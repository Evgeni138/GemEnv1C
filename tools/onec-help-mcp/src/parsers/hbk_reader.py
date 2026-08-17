"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Модуль для чтения бинарных файлов справки 1С (.hbk/.res).

Извлечение документации из HBK файлов платформы 1С:Предприятие.
"""

import struct
import zipfile
import io
import logging
from typing import Dict, List, Optional, Tuple, BinaryIO
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class HbkEntity:
    """Сущность в HBK файле"""
    name: str
    header_address: int
    body_address: int
    reserved: int

@dataclass
class TocChunk:
    """Чанк оглавления"""
    id: int
    parent_id: int
    child_count: int
    child_ids: List[int]
    title_ru: str
    title_en: str
    html_path: str

@dataclass
class TocPage:
    """Страница оглавления"""
    title_ru: str
    title_en: str
    html_path: str
    children: List['TocPage']

class HbkContainerReader:
    """Читатель HBK контейнеров"""
    
    BYTES_BY_FILE_INFOS = 12  # int * 4
    
    def __init__(self):
        self.entities: Dict[str, HbkEntity] = {}
        self.buffer: bytes = b''
    
    def read_hbk(self, path: Path) -> Dict[str, bytes]:
        """
        Читает HBK файл и извлекает все сущности
        
        Args:
            path: Путь к HBK файлу
            
        Returns:
            Словарь с именами сущностей и их содержимым
        """
        if not path.exists():
            raise FileNotFoundError(f"HBK файл не найден: {path}")
        
        logger.info(f"Чтение HBK файла: {path}")
        
        with open(path, 'rb') as f:
            self.buffer = f.read()
        
        # Парсим структуру файла
        self._parse_entities()
        
        # Извлекаем содержимое сущностей
        entities_content = {}
        for name, entity in self.entities.items():
            try:
                content = self._get_entity_body(entity.body_address)
                entities_content[name] = content
                logger.debug(f"Извлечена сущность: {name}, размер: {len(content)} байт")
            except Exception as e:
                logger.warning(f"Ошибка извлечения сущности {name}: {e}")
        
        return entities_content
    
    def _parse_entities(self):
        """Парсит список сущностей из HBK файла"""
        buffer = self.buffer
        pos = 0
        
        # Пропускаем заголовок (16 байт)
        pos += 16
        
        # Читаем размеры
        pos += 2  # short
        payload_size = self._get_long_string(buffer, pos)
        pos += 9  # размер строки + 1 байт
        block_size = self._get_long_string(buffer, pos)
        pos += 9  # размер строки + 1 байт
        pos += 11  # long + byte + short
        
        # Читаем информацию о файлах
        file_infos_start = pos
        file_infos = buffer[pos:pos + payload_size]
        pos += block_size
        
        # Парсим информацию о файлах
        file_infos_pos = 0
        count = len(file_infos) // self.BYTES_BY_FILE_INFOS
        
        for i in range(count):
            # Читаем адреса
            header_address = struct.unpack('<I', file_infos[file_infos_pos:file_infos_pos + 4])[0]
            file_infos_pos += 4
            body_address = struct.unpack('<I', file_infos[file_infos_pos:file_infos_pos + 4])[0]
            file_infos_pos += 4
            reserved = struct.unpack('<I', file_infos[file_infos_pos:file_infos_pos + 4])[0]
            file_infos_pos += 4
            
            if reserved != 0x7FFFFFFF:  # Int.MAX_VALUE
                continue
            
            # Получаем имя файла
            name = self._get_entity_name(header_address)
            if name:
                self.entities[name] = HbkEntity(name, header_address, body_address, reserved)
                logger.debug(f"Найдена сущность: {name} (header: {header_address}, body: {body_address})")
    
    def _get_long_string(self, buffer: bytes, pos: int) -> int:
        """Читает длинную строку (8 байт + 1) и возвращает как int"""
        string_bytes = buffer[pos:pos + 8]
        pos += 8
        pos += 1  # пропускаем разделитель
        
        try:
            return int(string_bytes.decode('ascii'), 16)
        except (ValueError, UnicodeDecodeError):
            return 0
    
    def _get_entity_name(self, header_address: int) -> Optional[str]:
        """Получает имя сущности по адресу заголовка"""
        try:
            buffer = self.buffer
            pos = header_address
            
            pos += 2  # пропускаем 2 байта
            payload_size = self._get_long_string(buffer, pos)
            pos += 9  # размер строки + 1 байт
            pos += 40  # пропускаем 40 байт
            
            # Читаем строку имени
            name_size = payload_size - 24  # вычитаем пропущенные байты
            if name_size > 0 and pos + name_size <= len(buffer):
                name_bytes = buffer[pos:pos + name_size]
                # Имя в UTF-16LE
                name = name_bytes.decode('utf-16le').rstrip('\x00')
                return name.strip('"')
        except Exception as e:
            logger.warning(f"Ошибка чтения имени сущности по адресу {header_address}: {e}")
        
        return None
    
    def _get_entity_body(self, body_address: int) -> bytes:
        """Получает содержимое сущности по адресу тела"""
        buffer = self.buffer
        pos = body_address
        
        pos += 2  # пропускаем 2 байта
        payload_size = self._get_long_string(buffer, pos)
        pos += 9  # размер строки + 1 байт
        pos += 20  # пропускаем 20 байт
        
        # Читаем тело
        if pos + payload_size <= len(buffer):
            return buffer[pos:pos + payload_size]
        else:
            raise ValueError(f"Недостаточно данных для чтения тела сущности")

class TocParser:
    """Парсер оглавления HBK файлов"""
    
    def __init__(self):
        self.chunks: List[TocChunk] = []
    
    def parse_toc(self, pack_block: bytes) -> List[TocPage]:
        """
        Парсит оглавление из сжатого блока
        
        Args:
            pack_block: Сжатые данные оглавления
            
        Returns:
            Список страниц оглавления
        """
        try:
            # Распаковываем данные
            decompressed = self._decompress_pack_block(pack_block)
            
            # Парсим текстовое содержимое
            # Пробуем сначала CP1251 (русская кодировка для справки 1С), затем UTF-8
            try:
                content = decompressed.decode('cp1251', errors='strict')
            except (UnicodeDecodeError, LookupError):
                try:
                    content = decompressed.decode('utf-8', errors='strict')
                except UnicodeDecodeError:
                    content = decompressed.decode('utf-8', errors='ignore')
            
            # Токенизируем и парсим
            tokens = self._tokenize(content)
            chunks = self._parse_chunks(tokens)
            
            # Строим дерево страниц
            return self._build_pages_tree(chunks)
            
        except Exception as e:
            logger.error(f"Ошибка парсинга оглавления: {e}")
            return []
    
    def _decompress_pack_block(self, data: bytes) -> bytes:
        """Распаковывает сжатый блок данных"""
        try:
            with zipfile.ZipFile(io.BytesIO(data), 'r') as zip_file:
                # Получаем первый файл из архива
                file_list = zip_file.namelist()
                if file_list:
                    return zip_file.read(file_list[0])
        except Exception as e:
            logger.warning(f"Ошибка распаковки PackBlock: {e}")
        
        return data
    
    def _tokenize(self, content: str) -> List[str]:
        """Токенизирует содержимое оглавления"""
        tokens = []
        current_token = ""
        in_string = False
        escape_next = False
        
        for char in content:
            if escape_next:
                current_token += char
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                current_token += char
                continue
            
            if char == '"':
                in_string = not in_string
                current_token += char
                continue
            
            if not in_string and char in '{}[](),':
                if current_token.strip():
                    tokens.append(current_token.strip())
                    current_token = ""
                tokens.append(char)
            else:
                current_token += char
        
        if current_token.strip():
            tokens.append(current_token.strip())
        
        return tokens
    
    def _parse_chunks(self, tokens: List[str]) -> List[TocChunk]:
        """Парсит чанки из токенов"""
        chunks = []
        i = 0
        
        while i < len(tokens):
            if tokens[i] == '{':
                chunk = self._parse_chunk(tokens, i)
                if chunk:
                    chunks.append(chunk)
                i = self._find_closing_brace(tokens, i) + 1
            else:
                i += 1
        
        return chunks
    
    def _parse_chunk(self, tokens: List[str], start: int) -> Optional[TocChunk]:
        """Парсит отдельный чанк"""
        try:
            i = start + 1  # пропускаем открывающую скобку
            
            # ID
            if i >= len(tokens) or not tokens[i].isdigit():
                return None
            chunk_id = int(tokens[i])
            i += 1
            
            # Parent ID
            if i >= len(tokens) or not tokens[i].isdigit():
                return None
            parent_id = int(tokens[i])
            i += 1
            
            # Child count
            if i >= len(tokens) or not tokens[i].isdigit():
                return None
            child_count = int(tokens[i])
            i += 1
            
            # Child IDs
            child_ids = []
            for _ in range(child_count):
                if i >= len(tokens) or not tokens[i].isdigit():
                    break
                child_ids.append(int(tokens[i]))
                i += 1
            
            # Пропускаем до закрывающей скобки
            i = self._find_closing_brace(tokens, i)
            
            # Создаем чанк (заголовки и пути будут заполнены позже)
            return TocChunk(
                id=chunk_id,
                parent_id=parent_id,
                child_count=child_count,
                child_ids=child_ids,
                title_ru="",
                title_en="",
                html_path=""
            )
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга чанка: {e}")
            return None
    
    def _find_closing_brace(self, tokens: List[str], start: int) -> int:
        """Находит закрывающую скобку для открывающей"""
        brace_count = 1
        i = start + 1
        
        while i < len(tokens) and brace_count > 0:
            if tokens[i] == '{':
                brace_count += 1
            elif tokens[i] == '}':
                brace_count -= 1
            i += 1
        
        return i - 1
    
    def _build_pages_tree(self, chunks: List[TocChunk]) -> List[TocPage]:
        """Строит дерево страниц из чанков"""
        # Создаем словарь для быстрого поиска
        chunks_dict = {chunk.id: chunk for chunk in chunks}
        
        # Создаем страницы
        pages_dict = {}
        for chunk in chunks:
            page = TocPage(
                title_ru=f"Page {chunk.id}",
                title_en=f"Page {chunk.id}",
                html_path=f"page_{chunk.id}.html",
                children=[]
            )
            pages_dict[chunk.id] = page
        
        # Строим иерархию
        root_pages = []
        for chunk in chunks:
            page = pages_dict[chunk.id]
            if chunk.parent_id == 0:
                root_pages.append(page)
            else:
                parent_page = pages_dict.get(chunk.parent_id)
                if parent_page:
                    parent_page.children.append(page)
        
        return root_pages

class HbkHelpReader:
    """Основной класс для чтения справки из HBK файлов"""
    
    def __init__(self):
        self.container_reader = HbkContainerReader()
        self.toc_parser = TocParser()
    
    def read_help_file(self, hbk_path: Path) -> Dict[str, any]:
        """
        Читает HBK файл и извлекает всю справку
        
        Args:
            hbk_path: Путь к HBK файлу
            
        Returns:
            Словарь с извлеченной справкой
        """
        logger.info(f"Чтение справки из HBK файла: {hbk_path}")
        
        try:
            # Извлекаем сущности
            entities = self.container_reader.read_hbk(hbk_path)
            
            result = {
                'entities': entities,
                'toc_pages': [],
                'html_files': {}
            }
            
            # Парсим оглавление если есть PackBlock
            if 'PackBlock' in entities:
                toc_pages = self.toc_parser.parse_toc(entities['PackBlock'])
                result['toc_pages'] = toc_pages
                logger.info(f"Извлечено {len(toc_pages)} страниц оглавления")
            
            # Извлекаем HTML файлы если есть FileStorage
            if 'FileStorage' in entities:
                html_files = self._extract_html_files(entities['FileStorage'])
                result['html_files'] = html_files
                logger.info(f"Извлечено {len(html_files)} HTML файлов")
            
            return result
            
        except (zipfile.BadZipFile, struct.error, ValueError) as e:
            # Файл не является валидным HBK файлом, это нормально для некоторых .res файлов
            logger.debug(f"Файл {hbk_path.name} не является валидным HBK файлом: {type(e).__name__}")
            return {}
        except Exception as e:
            logger.warning(f"Ошибка чтения HBK файла {hbk_path.name}: {e}")
            return {}
    
    def _extract_html_files(self, file_storage: bytes) -> Dict[str, str]:
        """Извлекает HTML файлы из FileStorage"""
        html_files = {}
        
        try:
            with zipfile.ZipFile(io.BytesIO(file_storage), 'r') as zip_file:
                for file_name in zip_file.namelist():
                    # Фильтруем только HTML файлы справки 1С
                    if self._is_valid_help_file(file_name):
                        try:
                            # Пробуем сначала CP1251 (русская кодировка для справки 1С), затем UTF-8
                            try:
                                content = zip_file.read(file_name).decode('cp1251', errors='strict')
                            except (UnicodeDecodeError, LookupError):
                                try:
                                    content = zip_file.read(file_name).decode('utf-8', errors='strict')
                                except UnicodeDecodeError:
                                    content = zip_file.read(file_name).decode('utf-8', errors='ignore')
                            # Дополнительная проверка содержимого
                            if self._is_help_content(content):
                                html_files[file_name] = content
                                logger.debug(f"Извлечен файл справки: {file_name}")
                        except Exception as e:
                            logger.warning(f"Ошибка чтения HTML файла {file_name}: {e}")
        except zipfile.BadZipFile:
            # FileStorage не является zip-архивом, это нормально для некоторых файлов
            logger.debug(f"FileStorage не является zip-архивом (это нормально для некоторых файлов)")
            return {}
        except Exception as e:
            logger.debug(f"Ошибка извлечения HTML файлов: {e}")
        
        return html_files
    
    def _is_valid_help_file(self, file_name: str) -> bool:
        """Проверяет, является ли файл валидным файлом справки 1С"""
        # Исключаем файлы, которые точно не являются справкой
        excluded_patterns = [
            '.css',
            '.js',
            '.png',
            '.jpg',
            '.jpeg',
            '.gif',
            '.ico',
            '.woff',
            '.woff2',
            '.ttf',
            '.eot',
            'license',
            'copyright',
            'apache',
            'sil',
            'boost',
            'libogg',
            'jsoncons',
            'boutros',
            'xiph',
            'v8update',
            'style',
            'script'
        ]
        
        file_name_lower = file_name.lower()
        
        # Проверяем исключения
        for pattern in excluded_patterns:
            if pattern in file_name_lower:
                return False
        
        # Должен быть HTML файл
        if not file_name.endswith('.html'):
            return False
        
        # Должен содержать пути, характерные для справки 1С
        help_paths = [
            'global-methods',
            'global-properties', 
            'objects',
            'enums',
            'constructors',
            'methods',
            'properties',
            'events',
            'functions',
            'types'
        ]
        
        return any(path in file_name_lower for path in help_paths)
    
    def _is_help_content(self, content: str) -> bool:
        """Проверяет, является ли содержимое справкой 1С"""
        content_lower = content.lower()
        
        # Исключаем файлы с лицензиями и копирайтами
        excluded_content = [
            'apache license',
            'sil open font license',
            'boost software license',
            'copyright',
            'license',
            'font software',
            'redistribution',
            'permission is hereby granted',
            'libogg',
            'jsoncons',
            'boutros international',
            'xiph.org foundation'
        ]
        
        for pattern in excluded_content:
            if pattern in content_lower:
                return False
        
        # Должен содержать элементы справки 1С
        help_indicators = [
            'синтаксис',
            'параметры',
            'возвращаемое значение',
            'описание',
            'пример',
            'методы',
            'свойства',
            'события',
            'перечисление',
            'объект',
            'функция',
            'syntax',
            'parameters',
            'return value',
            'description',
            'example',
            'methods',
            'properties',
            'events',
            'enumeration',
            'object',
            'function'
        ]
        
        return any(indicator in content_lower for indicator in help_indicators)

# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Тестируем на реальном HBK файле
    hbk_path = Path("/opt/1cv8/8.5.1.397/shcntx_ru.hbk")
    
    if hbk_path.exists():
        reader = HbkHelpReader()
        result = reader.read_help_file(hbk_path)
        
        print(f"Найдено сущностей: {len(result.get('entities', {}))}")
        print(f"Страниц оглавления: {len(result.get('toc_pages', []))}")
        print(f"HTML файлов: {len(result.get('html_files', {}))}")
        
        # Показываем первые несколько HTML файлов
        for i, (name, content) in enumerate(list(result.get('html_files', {}).items())[:3]):
            print(f"\nHTML файл {i+1}: {name}")
            print(f"Размер: {len(content)} символов")
            print(f"Начало: {content[:200]}...")
    else:
        print(f"HBK файл не найден: {hbk_path}")
