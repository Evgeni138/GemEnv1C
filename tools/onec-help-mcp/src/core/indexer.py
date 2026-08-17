"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Модуль индексации справки 1С с поддержкой версионирования
"""

import logging
import asyncio
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from ..config.version import get_help_path_for_version, normalize_version
from ..config.settings import CACHE_DIR
from ..services.embedding import get_embedding_service
from ..services.qdrant import get_qdrant_service
from ..core.api_element import ApiElementNormalizer, ApiElement
from ..utils.indexing_status import update_status, reset_status
try:
    from ..parsers.hbk_reader import HbkHelpReader
    from ..parsers.html_parser import HtmlParser
    PARSERS_AVAILABLE = True
except ImportError:
    HbkHelpReader = None
    HtmlParser = None
    PARSERS_AVAILABLE = False

# Настраиваем логирование для шумных библиотек ДО импорта
# httpx - HTTP клиент (используется для запросов к embedding service и qdrant)
logging.getLogger("httpx").setLevel(logging.WARNING)
# httpcore - низкоуровневый HTTP клиент (используется httpx)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpcore.http11").setLevel(logging.WARNING)
logging.getLogger("httpcore.connection").setLevel(logging.WARNING)
# qdrant_client - может логировать HTTP запросы через httpx
logging.getLogger("qdrant_client").setLevel(logging.WARNING)

# Логирование настраивается в server.py (логгер src.* не пропагирует в root — один вывод)
logger = logging.getLogger(__name__)


def _get_source_priority(html_path: str) -> int:
    """
    Определяет приоритет источника HTML файла для выбора более релевантного элемента.
    Большее значение = более релевантный источник.
    
    Args:
        html_path: Путь к HTML файлу
        
    Returns:
        Приоритет источника (0-10)
    """
    if not html_path:
        return 0
    
    path_lower = html_path.lower()
    
    # Высший приоритет: страницы методов
    if '/methods/' in path_lower:
        return 10
    # Высокий приоритет: страницы свойств (отдельные страницы с детальной информацией)
    if '/properties/' in path_lower:
        return 9
    # Высокий приоритет: страницы конструкторов
    if '/constructors/' in path_lower or '/ctors/' in path_lower:
        return 8
    # Средний приоритет: страницы объектов/типов
    if '/object' in path_lower and not '/events/' in path_lower:
        return 5
    # Низкий приоритет: страницы событий
    if '/events/' in path_lower:
        return 2
    # Низкий приоритет: страницы функций
    if '/functions/' in path_lower or '/global' in path_lower:
        return 3
    
    return 1


class HelpIndexer:
    """Класс для индексации справки 1С с поддержкой версий"""
    
    def __init__(self, version: str):
        """
        Инициализация индексатора для конкретной версии
        
        Args:
            version: Версия платформы (например, "8.3.24")
        """
        self.version = normalize_version(version)
        self.help_path = get_help_path_for_version(self.version)
        self.embedding_service = get_embedding_service()
        self.qdrant_service = get_qdrant_service()
        self.hbk_reader = HbkHelpReader() if PARSERS_AVAILABLE and HbkHelpReader else None
        self.html_parser = HtmlParser() if PARSERS_AVAILABLE and HtmlParser else None
        
        logger.info(f"📚 Инициализация индексатора для версии {self.version}, путь: {self.help_path}")
    
    async def index_version(self) -> bool:
        """
        Индексирует справку для версии платформы
        
        Returns:
            True если индексация успешна, False иначе
        """
        collection_name = self._get_collection_name()
        
        try:
            # Сбрасываем статус и инициализируем новую индексацию
            reset_status(self.version)
            update_status(
                self.version,
                status="parsing",
                collection_name=collection_name
            )
            
            if not self.help_path.exists():
                error_msg = f"Папка справки не найдена: {self.help_path}"
                logger.error(f"❌ {error_msg}")
                update_status(self.version, status="error", error_message=error_msg)
                return False
            
            logger.info(f"🚀 Начало индексации справки для версии {self.version}")
            
            # Шаг 1: Парсинг HBK файлов
            help_items = await self._parse_help_files()
            if not help_items:
                error_msg = f"Не найдено элементов справки для версии {self.version}"
                logger.warning(f"⚠️ {error_msg}")
                update_status(self.version, status="error", error_message=error_msg)
                return False
            
            logger.info(f"✅ Найдено {len(help_items)} элементов справки")
            
            # Обновляем статус: парсинг завершен, начинаем построение BM25
            update_status(
                self.version,
                status="building_bm25",
                total_items=len(help_items)
            )
            
            # Шаг 2: Построение BM25 корпуса
            # Используем text для всех элементов
            corpus = [item.get('text', '') for item in help_items if item.get('text')]
            
            logger.info(f"🏗️ Построение BM25 корпуса для коллекции '{collection_name}'...")
            bm25_built = await self.embedding_service.build_bm25_corpus(corpus, collection_name)
            if not bm25_built:
                error_msg = f"Не удалось построить BM25 корпус для коллекции '{collection_name}'"
                logger.error(f"❌ {error_msg}")
                update_status(self.version, status="error", error_message=error_msg)
                return False
            
            # Обновляем статус: начинаем векторизацию
            update_status(self.version, status="vectorizing")
            
            # Шаг 3: Векторизация и сохранение в Qdrant
            await self._vectorize_and_save(help_items, collection_name)
            
            logger.info(f"✅ Индексация справки для версии {self.version} завершена успешно")
            update_status(self.version, status="completed")
            return True
            
        except Exception as e:
            error_msg = f"Ошибка индексации справки для версии {self.version}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            import traceback
            logger.error(traceback.format_exc())
            update_status(self.version, status="error", error_message=error_msg)
            return False
    
    async def _parse_help_files(self) -> List[Dict[str, Any]]:
        """
        Парсит HBK файлы и извлекает элементы справки
        
        Returns:
            Список элементов справки с текстом и метаданными
        """
        help_items = []
        
        # Поиск HBK файлов - фильтруем только валидные файлы справки
        # Обрабатываем только файлы с суффиксом _ru (русская справка)
        # Файлы _root обычно содержат только структуру без контента
        hbk_files = []
        
        # Сначала ищем .hbk файлы с суффиксом _ru
        hbk_files.extend([f for f in self.help_path.rglob('*_ru.hbk') if f.is_file()])
        
        # Также обрабатываем .res файлы с суффиксом _ru (но они должны быть валидными HBK)
        res_files = [f for f in self.help_path.rglob('*_ru.res') if f.is_file()]
        
        # Проверяем валидность .res файлов перед добавлением (I/O в thread, чтобы не блокировать event loop)
        def _read_res_header(path: Path) -> Optional[bytes]:
            try:
                with open(path, 'rb') as f:
                    return f.read(16)
            except Exception:
                return None

        for res_file in res_files:
            try:
                header = await asyncio.to_thread(_read_res_header, res_file)
                if header and len(header) >= 16:
                    hbk_files.append(res_file)
            except Exception:
                continue
        
        if not hbk_files:
            logger.warning(f"⚠️ Не найдено валидных HBK файлов в {self.help_path}")
            logger.info(f"💡 Ищем файлы с суффиксом *_ru.hbk и *_ru.res")
            return help_items
        
        logger.info(f"📖 Найдено {len(hbk_files)} валидных HBK файлов для обработки")
        
        if not self.hbk_reader or not self.html_parser:
            logger.error("❌ HBK reader или HTML parser недоступны")
            return help_items
        
        # Обработка каждого HBK файла
        processed_files = 0
        skipped_files = 0
        
        for hbk_file in hbk_files:
            try:
                logger.info(f"📖 Обработка HBK файла: {hbk_file.name}")
                
                # Читаем HBK файл (sync I/O в thread, чтобы не блокировать event loop)
                hbk_data = await asyncio.to_thread(self.hbk_reader.read_help_file, hbk_file)
                if not hbk_data:
                    skipped_files += 1
                    logger.debug(f"⚠️ Файл {hbk_file.name} не содержит данных справки, пропускаем")
                    continue
                
                # Проверяем, что файл содержит HTML контент
                html_files = hbk_data.get('html_files', {})
                if not html_files:
                    skipped_files += 1
                    logger.debug(f"⚠️ Файл {hbk_file.name} не содержит HTML файлов, пропускаем")
                    continue
                
                processed_files += 1
                logger.info(f"✅ Файл {hbk_file.name}: извлечено {len(html_files)} HTML файлов")
                
                for html_path, html_content in html_files.items():
                    try:
                        # Парсим HTML содержимое
                        parsed_data = self.html_parser.parse_html_content(html_content, html_path)
                        
                        if parsed_data.get('type') == 'error':
                            continue
                        
                        # Нормализуем данные в список ApiElement
                        api_elements = ApiElementNormalizer.normalize_parsed_data(
                            parsed_data=parsed_data,
                            platform_version=self.version,
                            file_path=f"{hbk_file.name}:{html_path}",
                            hbk_source=str(hbk_file),
                            hbk_html_path=html_path
                        )
                        
                        # Если нормализация не дала результатов, создаем базовый элемент страницы
                        if not api_elements:
                            # Создаем базовый элемент для страницы
                            text = self._build_index_text(parsed_data, hbk_file, html_path)
                            string_id = f"{self.version}_{hbk_file.stem}_{html_path}"
                            point_id = int(hashlib.md5(string_id.encode('utf-8')).hexdigest()[:15], 16) & 0x7FFFFFFFFFFFFFFF
                            
                            item = {
                                'id': point_id,
                                'original_id': string_id,
                                'title': parsed_data.get('title', html_path),
                                'text': text,
                                'content': parsed_data.get('content', ''),
                                'type': parsed_data.get('type', 'unknown'),
                                'file_path': f"{hbk_file.name}:{html_path}",
                                'hbk_source': str(hbk_file),
                                'hbk_html_path': html_path,
                                'platform_version': self.version,
                                'metadata': self._extract_metadata(parsed_data),
                                'is_api_element': False  # Флаг для старых записей
                            }
                            help_items.append(item)
                        else:
                            # Преобразуем ApiElement в формат для индексации
                            for api_element in api_elements:
                                element_id = api_element.get_id()
                                
                                # Проверяем, не был ли уже добавлен элемент с таким ID
                                # Если был, выбираем более релевантный источник
                                existing_item = None
                                for existing in help_items:
                                    if existing.get('id') == element_id:
                                        existing_item = existing
                                        break
                                
                                # Определяем приоритет источника (methods/ > constructors/ > events/)
                                current_priority = _get_source_priority(api_element.hbk_html_path)
                                
                                if existing_item:
                                    existing_priority = _get_source_priority(existing_item.get('hbk_html_path', ''))
                                    # Если текущий источник менее релевантный, пропускаем
                                    if current_priority < existing_priority:
                                        logger.debug(f"⏭️ Пропускаем {api_element.full_name} из {api_element.hbk_html_path} (уже есть более релевантный источник)")
                                        continue
                                    # Если текущий источник более релевантный, заменяем
                                    elif current_priority > existing_priority:
                                        logger.debug(f"🔄 Заменяем {api_element.full_name} более релевантным источником: {api_element.hbk_html_path}")
                                        help_items.remove(existing_item)
                                    # Если приоритеты равны, оставляем первый (не перезаписываем)
                                    else:
                                        logger.debug(f"⏭️ Пропускаем дубликат {api_element.full_name} из {api_element.hbk_html_path}")
                                        continue
                                
                                item = {
                                    'id': element_id,
                                    'original_id': api_element.get_original_id(),
                                    'title': api_element.full_name,
                                    'text': api_element.search_text,
                                    'content': api_element.description,
                                    'type': api_element.element_type.value,
                                    'file_path': api_element.file_path,
                                    'hbk_source': api_element.hbk_source,
                                    'hbk_html_path': api_element.hbk_html_path,
                                    'platform_version': api_element.platform_version,
                                    'metadata': {
                                        'element_type': api_element.element_type.value,
                                        'name': api_element.name,
                                        'name_en': api_element.name_en,
                                        'full_name': api_element.full_name,
                                        'parent_type': api_element.parent_type,
                                        'details': api_element.details
                                    },
                                    'is_api_element': True  # Флаг для новых записей
                                }
                                help_items.append(item)
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка парсинга HTML файла {html_path}: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())
                        continue
                
            except Exception as e:
                skipped_files += 1
                logger.warning(f"⚠️ Ошибка обработки HBK файла {hbk_file.name}: {e}")
                continue
        
        logger.info(f"✅ Обработано файлов: {processed_files}, пропущено: {skipped_files}, извлечено элементов: {len(help_items)}")
        return help_items
    
    def _build_index_text(self, parsed_data: Dict[str, Any], hbk_file: Path, html_path: str) -> str:
        """
        Формирует текст для индексации из распарсенных данных
        
        Args:
            parsed_data: Распарсенные данные из HTML
            hbk_file: Путь к HBK файлу
            html_path: Путь к HTML файлу внутри HBK
            
        Returns:
            Текст для индексации
        """
        text_parts = []
        
        # Заголовок
        title = parsed_data.get('title', '')
        if title:
            text_parts.append(title)
        
        # Описание
        content = parsed_data.get('content', '')
        if content:
            text_parts.append(content)
        
        # Функции
        for func in parsed_data.get('functions', []):
            func_text = f"Функция {func.name}"
            if func.description:
                func_text += f": {func.description}"
            if func.parameters:
                func_text += f"\nПараметры: {func.parameters}"
            if func.return_type:
                func_text += f"\nВозвращает: {func.return_type}"
            text_parts.append(func_text)
        
        # Объекты
        for obj in parsed_data.get('objects', []):
            obj_text = f"Объект {obj.name}"
            if obj.description:
                obj_text += f": {obj.description}"
            if obj.methods:
                obj_text += f"\nМетоды: {', '.join([m.name for m in obj.methods])}"
            if obj.properties:
                obj_text += f"\nСвойства: {', '.join([p.get('name', '') for p in obj.properties])}"
            text_parts.append(obj_text)
        
        # Перечисления
        for enum in parsed_data.get('enums', []):
            enum_text = f"Перечисление {enum.name}"
            if enum.description:
                enum_text += f": {enum.description}"
            if enum.values:
                enum_text += f"\nЗначения: {', '.join([v.get('name', '') for v in enum.values])}"
            text_parts.append(enum_text)
        
        return "\n\n".join(text_parts)
    
    def _extract_metadata(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Извлекает метаданные из распарсенных данных"""
        metadata = {
            'type': parsed_data.get('type', 'unknown')
        }
        
        # Добавляем информацию о функциях, объектах, перечислениях
        if parsed_data.get('functions'):
            metadata['functions'] = [
                {
                    'name': f.name,
                    'description': f.description,
                    'parameters': f.parameters,
                    'return_type': f.return_type
                }
                for f in parsed_data['functions']
            ]
        
        if parsed_data.get('objects'):
            metadata['objects'] = [
                {
                    'name': o.name,
                    'description': o.description,
                    'methods': [m.name for m in o.methods],
                    'properties': [p.get('name', '') for p in o.properties]
                }
                for o in parsed_data['objects']
            ]
        
        if parsed_data.get('enums'):
            metadata['enums'] = [
                {
                    'name': e.name,
                    'description': e.description,
                    'values': [v.get('name', '') for v in e.values]
                }
                for e in parsed_data['enums']
            ]
        
        return metadata
    
    async def _vectorize_and_save(
        self,
        help_items: List[Dict[str, Any]],
        collection_name: str
    ):
        """
        Векторизует элементы справки и сохраняет в Qdrant
        
        Args:
            help_items: Список элементов справки
            collection_name: Имя коллекции Qdrant
        """
        # Убеждаемся, что коллекция существует
        await self.qdrant_service.ensure_collection_exists_async(collection_name)
        
        # Векторизуем и сохраняем батчами
        batch_size = 50
        total_batches = (len(help_items) + batch_size - 1) // batch_size
        
        # Обновляем статус с общим количеством батчей
        update_status(self.version, total_batches=total_batches)

        logger.info(f"📦 Векторизация и сохранение {len(help_items)} элементов в {total_batches} батчах")
        logger.info(f"🌐 Embedding service URL: {self.embedding_service.embedding_url}")
        
        processed_items = 0
        
        for batch_idx in range(0, len(help_items), batch_size):
            batch = help_items[batch_idx:batch_idx + batch_size]
            batch_num = (batch_idx // batch_size) + 1

            try:
                # Обновляем статус: текущий батч
                update_status(self.version, current_batch=batch_num)

                # Логируем прогресс для каждого батча
                logger.info(f"📦 Обработка батча {batch_num}/{total_batches} ({len(batch)} элементов)")

                # Извлекаем тексты из батча
                batch_texts = [item['text'] for item in batch]

                # Параллельная векторизация всего батча
                logger.debug(f"🔄 Параллельная векторизация {len(batch_texts)} текстов...")
                dense_vectors, sparse_embeddings = await asyncio.gather(
                    self.embedding_service.get_dense_embeddings_batch(batch_texts),
                    self.embedding_service.get_sparse_embeddings_batch(batch_texts, collection_name)
                )

                # Формируем points из векторизованных данных
                points = []
                for idx, item in enumerate(batch):
                    try:
                        # Получаем dense вектор для текущего элемента
                        dense_vector = dense_vectors[idx] if idx < len(dense_vectors) else None
                        if not dense_vector:
                            logger.warning(f"⚠️ Не удалось получить dense эмбеддинг для {item['id']}")
                            continue

                        # Получаем sparse эмбеддинг для текущего элемента
                        sparse_embedding = sparse_embeddings[idx] if idx < len(sparse_embeddings) else {"indices": [], "values": []}
                        
                        # Формируем payload для Qdrant
                        payload = {
                            'original_id': item.get('original_id', str(item['id'])),
                            'title': item['title'],
                            'text': item['text'],
                            'content': item.get('content', ''),
                            'type': item['type'],
                            'file_path': item['file_path'],
                            'hbk_source': item['hbk_source'],
                            'hbk_html_path': item['hbk_html_path'],
                            'platform_version': item['platform_version'],
                            'metadata': item.get('metadata', {}),
                            'is_api_element': item.get('is_api_element', False)
                        }
                        
                        # Добавляем поля для API элементов для быстрого поиска
                        if item.get('is_api_element'):
                            metadata = item.get('metadata', {})
                            payload.update({
                                'element_type': metadata.get('element_type', ''),
                                'element_name': metadata.get('name', ''),
                                'element_name_en': metadata.get('name_en', ''),
                                'full_name': metadata.get('full_name', ''),
                                'parent_type': metadata.get('parent_type')
                            })
                        
                        point = {
                            'id': item['id'],
                            'vector': dense_vector,
                            'sparse_vector': sparse_embedding,
                            'payload': payload
                        }
                        points.append(point)
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка векторизации элемента {item.get('id', 'unknown')}: {e}")
                        import traceback
                        logger.debug(f"Traceback: {traceback.format_exc()}")
                        continue
                
                # Сохраняем батч в Qdrant
                if points:
                    try:
                        # Проверяем существование коллекции перед каждым батчем (на случай если она была удалена)
                        if not await self.qdrant_service.collection_exists_async(collection_name):
                            logger.warning(f"⚠️ Коллекция '{collection_name}' не существует, пересоздаем...")
                            await self.qdrant_service.ensure_collection_exists_async(collection_name)
                        
                        success = await self.qdrant_service.upsert_points_async(collection_name, points)
                        if success:
                            processed_items += len(points)
                            # Обновляем статус: количество обработанных элементов и точек
                            # Получаем актуальное количество точек из Qdrant
                            try:
                                collection_info = await self.qdrant_service.get_collection_info_async(collection_name)
                                points_count = collection_info.get("points_count", 0) if collection_info else 0
                            except Exception:
                                points_count = processed_items

                            update_status(
                                self.version,
                                processed_items=processed_items,
                                points_count=points_count
                            )
                            logger.info(f"✅ Батч {batch_num}/{total_batches} сохранен ({len(points)} точек)")
                        else:
                            logger.error(f"❌ Ошибка сохранения батча {batch_num}/{total_batches}")
                    except Exception as e:
                        logger.error(f"❌ Исключение при сохранении батча {batch_num}/{total_batches}: {e}")
                        import traceback
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        # Продолжаем со следующим батчем
                        continue
                else:
                    logger.warning(f"⚠️ Батч {batch_num}/{total_batches} не содержит точек для сохранения")
                    
            except Exception as e:
                logger.error(f"❌ Критическая ошибка при обработке батча {batch_num}/{total_batches}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Продолжаем со следующим батчем
                continue
        
        logger.info(f"✅ Векторизация и сохранение завершены")
    
    def _get_collection_name(self) -> str:
        """Получает имя коллекции Qdrant для версии"""
        from ..config.version import get_collection_name
        return get_collection_name(self.version)


async def index_all_versions() -> Dict[str, bool]:
    """
    Индексирует все доступные версии платформы
    
    Returns:
        Словарь {версия: успех_индексации}
    """
    from ..config.version import get_available_versions
    
    versions = await asyncio.to_thread(get_available_versions)
    if not versions:
        logger.warning("⚠️ Не найдено доступных версий платформы")
        return {}
    
    results = {}
    for version in versions:
        logger.info(f"🚀 Индексация версии {version}")
        indexer = HelpIndexer(version)
        success = await indexer.index_version()
        results[version] = success
    
    return results

