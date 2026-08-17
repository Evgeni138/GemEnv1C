"""
HTML парсер для извлечения документации из HTML файлов справки 1С

Парсит HTML файлы, извлеченные из HBK файлов, и создает структурированную
документацию для BSL контекста.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from bs4 import BeautifulSoup, Tag
from html import unescape

logger = logging.getLogger(__name__)

@dataclass
class BslParameter:
    """Параметр функции/метода"""
    name: str
    type: str
    description: str
    required: bool = True
    default_value: Optional[str] = None

@dataclass
class BslFunction:
    """Функция BSL"""
    name: str
    name_en: str = ""  # Английское имя
    description: str = ""
    parameters: List[BslParameter] = field(default_factory=list)
    return_type: str = "Unknown"
    return_description: str = ""
    examples: List[str] = field(default_factory=list)
    category: str = "Unknown"
    signature: str = ""  # Полная сигнатура функции
    since_version: str = ""  # Версия платформы, с которой доступна
    deprecated: bool = False
    deprecated_since: str = ""
    parent_type: Optional[str] = None  # Для методов объектов
    notes: str = ""  # Примечания
    availability: str = ""  # Доступность (сервер/клиент)
    related_elements: List[str] = field(default_factory=list)  # Связанные элементы ("См. также")

@dataclass
class BslProperty:
    """Свойство объекта"""
    name: str
    name_en: str = ""
    type: str = "Unknown"
    description: str = ""
    read_only: bool = False
    write_only: bool = False
    since_version: str = ""
    notes: str = ""  # Примечания
    availability: str = ""  # Доступность (сервер/клиент)
    parent_type: str = ""  # Родительский тип (для свойств из отдельных страниц)

@dataclass
class BslConstructor:
    """Конструктор объекта"""
    signature: str = ""
    parameters: List[BslParameter] = field(default_factory=list)
    description: str = ""
    examples: List[str] = field(default_factory=list)
    since_version: str = ""
    notes: str = ""  # Примечания
    availability: str = ""  # Доступность (сервер/клиент)

@dataclass
class BslObject:
    """Объект BSL"""
    name: str
    name_en: str = ""  # Английское имя
    description: str = ""
    methods: List[BslFunction] = field(default_factory=list)
    properties: List[BslProperty] = field(default_factory=list)
    constructors: List[BslConstructor] = field(default_factory=list)
    base_types: List[str] = field(default_factory=list)  # Базовые типы (наследование)
    events: List[Dict[str, str]] = field(default_factory=list)
    category: str = "Unknown"
    since_version: str = ""

@dataclass
class BslEnum:
    """Перечисление BSL"""
    name: str
    description: str
    values: List[Dict[str, str]]
    category: str

class HtmlParser:
    """Парсер HTML файлов справки 1С"""
    
    def __init__(self):
        self.functions: List[BslFunction] = []
        self.objects: List[BslObject] = []
        self.enums: List[BslEnum] = []
    
    def parse_html_content(self, html_content: str, file_path: str = "") -> Dict[str, any]:
        """
        Парсит HTML содержимое и извлекает BSL документацию
        
        Args:
            html_content: HTML содержимое
            file_path: Путь к файлу (для логирования)
            
        Returns:
            Словарь с извлеченной документацией
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Определяем тип страницы по содержимому
            page_type = self._detect_page_type(soup, file_path)
            
            result = {
                'type': page_type,
                'title': self._extract_title(soup),
                'content': self._extract_content(soup),
                'functions': [],
                'objects': [],
                'enums': [],
                'constructors': [],
                'properties': []
            }
            
            # Парсим в зависимости от типа страницы
            if page_type == 'function':
                # Проверяем, является ли это методом объекта (по пути или заголовку)
                title = self._extract_title(soup)
                is_method = '/methods/' in file_path or self._is_method_page(title, file_path)
                
                # Проверяем, является ли это функцией глобального контекста
                is_global_function = 'Глобальный контекст' in title or 'Global context' in title
                
                if is_method and not is_global_function:
                    # Парсим как метод объекта
                    method = self._parse_method_page(soup, file_path)
                    if method:
                        result['functions'] = [method]  # Методы хранятся как функции с parent_type
                        self.functions.append(method)
                else:
                    # Парсим как обычную функцию (включая функции глобального контекста)
                    function = self._parse_function_page(soup, file_path)
                    if function:
                        # Для функций глобального контекста убираем parent_type, если он был установлен
                        if is_global_function and hasattr(function, 'parent_type'):
                            function.parent_type = None
                        result['functions'] = [function]
                        self.functions.append(function)
            elif page_type == 'constructor':
                # Парсим страницу конструктора
                constructor = self._parse_constructor_page(soup, file_path)
                if constructor:
                    result['constructors'] = [constructor]
            elif page_type == 'object':
                obj = self._parse_object_page(soup, file_path)
                if obj:
                    result['objects'] = [obj]
                    self.objects.append(obj)
            elif page_type == 'property':
                # Парсим страницу свойства
                property_obj = self._parse_property_page(soup, file_path)
                if property_obj:
                    # Свойства добавляем в список свойств (для совместимости)
                    result['properties'] = [property_obj]
            elif page_type == 'enum':
                enum = self._parse_enum_page(soup, file_path)
                if enum:
                    result['enums'] = [enum]
                    self.enums.append(enum)
            elif page_type == 'index':
                # Парсим индексную страницу
                result.update(self._parse_index_page(soup, file_path))
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка парсинга HTML файла {file_path}: {e}")
            return {'type': 'error', 'error': str(e)}
    
    def _detect_page_type(self, soup: BeautifulSoup, file_path: str) -> str:
        """Определяет тип страницы по содержимому"""
        # Анализируем путь к файлу ПЕРВЫМ (приоритет)
        if '/methods/' in file_path:
            return 'function'  # Методы объектов парсятся как функции с parent_type
        elif '/constructors/' in file_path or '/ctors/' in file_path:
            return 'constructor'
        elif '/properties/' in file_path:
            return 'property'  # Страницы свойств
        elif '/enums/' in file_path:
            return 'enum'
        elif '/objects/' in file_path and '/methods/' not in file_path and '/events/' not in file_path and '/properties/' not in file_path:
            # Страница объекта (не метод, не событие, не свойство)
            return 'object'
        
        # Анализируем содержимое
        title = self._extract_title(soup)
        content = self._extract_content(soup)
        
        # Проверяем на функцию глобального контекста (до проверки объекта)
        # Функции глобального контекста обычно имеют формат "Глобальный контекст.ИмяФункции"
        if 'Глобальный контекст' in title or 'Global context' in title:
            if self._is_function_page(title, content):
                return 'function'
        
        # Проверяем на объект (но не если это метод в /methods/)
        if '/methods/' not in file_path and self._is_object_page(title, content):
            return 'object'
        
        # Проверяем на перечисление
        if self._is_enum_page(title, content):
            return 'enum'
        
        # Проверяем на функцию (после объекта и перечисления)
        if self._is_function_page(title, content):
            return 'function'
        
        # Проверяем на индексную страницу
        if self._is_index_page(title, content):
            return 'index'
        
        return 'unknown'
    
    def _is_function_page(self, title: str, content: str) -> bool:
        """Проверяет, является ли страница описанием функции"""
        function_indicators = [
            'Синтаксис:',
            'Параметры:',
            'Возвращаемое значение:',
            'Описание:',
            'Пример:'
        ]
        
        return any(indicator in content for indicator in function_indicators)
    
    def _is_method_page(self, title: str, file_path: str) -> bool:
        """Проверяет, является ли страница описанием метода объекта"""
        # Методы объектов обычно имеют формат "ТипОбъекта.ИмяМетода" в заголовке
        if '.' in title and not title.startswith('Глобальный'):
            # Проверяем, что это не глобальная функция
            parts = title.split('.')
            if len(parts) == 2:
                # Возможно, это метод объекта
                return True
        return False
    
    def _is_object_page(self, title: str, content: str) -> bool:
        """Проверяет, является ли страница описанием объекта"""
        object_indicators = [
            'Методы:',
            'Свойства:',
            'События:',
            'Объект',
            'Класс'
        ]
        
        return any(indicator in content for indicator in object_indicators)
    
    def _is_enum_page(self, title: str, content: str) -> bool:
        """Проверяет, является ли страница описанием перечисления"""
        enum_indicators = [
            'Значения:',
            'Элементы:',
            'Перечисление',
            'Enum'
        ]
        
        return any(indicator in content for indicator in enum_indicators)
    
    def _is_index_page(self, title: str, content: str) -> bool:
        """Проверяет, является ли страница индексной"""
        index_indicators = [
            'Содержание',
            'Оглавление',
            'Index',
            'Contents'
        ]
        
        return any(indicator in title for indicator in index_indicators)
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Извлекает заголовок страницы"""
        # Ищем заголовок в различных тегах
        title_selectors = [
            'h1',
            'h2',
            'title',
            '.title',
            '.header'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text().strip()
                if title:
                    return unescape(title)
        
        return ""
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Извлекает основное содержимое страницы"""
        # Удаляем скрипты и стили
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Ищем основное содержимое
        content_selectors = [
            '.content',
            '.main',
            '.body',
            'body',
            'div'
        ]
        
        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                content = element.get_text()
                if len(content.strip()) > 100:  # Достаточно длинное содержимое
                    return unescape(content)
        
        return soup.get_text()
    
    def _parse_function_page(self, soup: BeautifulSoup, file_path: str) -> Optional[BslFunction]:
        """Парсит страницу функции"""
        try:
            title = self._extract_title(soup)
            content = self._extract_content(soup)
            
            # Извлекаем имя функции из заголовка
            function_name = self._extract_function_name(title)
            
            # Извлекаем английское имя
            name_en = self._extract_english_name(title, content)
            
            # Извлекаем описание
            description = self._extract_description(content)
            
            # Извлекаем параметры (улучшенный парсинг для HTML структуры)
            parameters = self._extract_parameters_from_html(soup, content)
            
            # Извлекаем возвращаемое значение
            return_type, return_description = self._extract_return_value(content)
            
            # Извлекаем примеры (улучшенный парсинг для HTML структуры)
            examples = self._extract_examples_from_html(soup, content)
            
            # Извлекаем сигнатуру (после параметров, чтобы можно было построить полную)
            signature = self._extract_signature(content, function_name)
            
            # Если сигнатура неполная и есть параметры, строим полную сигнатуру
            if signature == function_name and parameters:
                param_strs = []
                for param in parameters:
                    param_str = param.name
                    if param.type and param.type != "Unknown":
                        param_str += f": {param.type}"
                    if not param.required:
                        param_str = f"[{param_str}]"
                    param_strs.append(param_str)
                if param_strs:
                    signature = f"{function_name}({', '.join(param_strs)})"
            
            # Извлекаем информацию о версии
            since_version, deprecated, deprecated_since = self._extract_version_info(content, soup)
            
            # Определяем категорию
            category = self._extract_category(file_path, content)
            
            # Извлекаем связи с другими API элементами (упоминания в описании)
            related_elements = self._extract_related_elements(content, function_name)
            
            # Извлекаем примечания и доступность
            notes = self._extract_notes(content)
            availability = self._extract_availability(content)
            
            func = BslFunction(
                name=function_name,
                name_en=name_en,
                description=description,
                parameters=parameters,
                return_type=return_type,
                return_description=return_description,
                examples=examples,
                category=category,
                signature=signature,
                since_version=since_version,
                deprecated=deprecated,
                deprecated_since=deprecated_since,
                notes=notes,
                availability=availability,
                related_elements=related_elements
            )
            
            return func
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга функции из {file_path}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _parse_constructor_page(self, soup: BeautifulSoup, file_path: str) -> Optional[BslConstructor]:
        """Парсит страницу конструктора объекта"""
        try:
            title = self._extract_title(soup)
            content = self._extract_content(soup)
            
            # Извлекаем родительский тип из заголовка или пути
            # Формат: "ДокументОбъект.Новый" или "Новый ДокументОбъект" или из пути
            parent_type = None
            if '.' in title:
                # Формат: "ДокументОбъект.Новый (DocumentObject.New)"
                title_before_brackets = re.split(r'\s*\(', title)[0]
                parts = title_before_brackets.split('.')
                if len(parts) >= 2:
                    parent_type = parts[0].strip()
            elif 'Новый' in title or 'New' in title:
                # Формат: "Новый ДокументОбъект" или "New DocumentObject"
                match = re.search(r'(?:Новый|New)\s+([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*(?:Объект|Object)?)', title)
                if match:
                    parent_type = match.group(1).strip()
            
            # Если не нашли в заголовке, пытаемся извлечь из пути
            if not parent_type and '/constructors/' in file_path:
                # Путь вида: objects/catalog125/catalog143/object146/constructors/New302.html
                # Ищем имя объекта в пути
                path_parts = file_path.split('/')
                for i, part in enumerate(path_parts):
                    if part == 'objects' and i + 1 < len(path_parts):
                        # Следующая часть может быть именем объекта или категорией
                        # Пропускаем категории и ищем objectXXX
                        for j in range(i + 1, len(path_parts)):
                            if path_parts[j].startswith('object') or path_parts[j].endswith('Object'):
                                # Это может быть объект, но нам нужно найти его имя на странице объекта
                                break
            
            # Извлекаем описание
            description = self._extract_description(content)
            
            # Извлекаем параметры (аналогично методам)
            parameters = self._extract_parameters_from_html(soup, content)
            
            # Извлекаем примеры
            examples = self._extract_examples_from_html(soup, content)
            
            # Извлекаем сигнатуру из HTML
            signature = self._extract_constructor_signature_from_html(soup, content)
            
            # Если сигнатура неполная и есть параметры, строим полную сигнатуру
            if not signature or signature == "Новый" or signature == "New":
                if parent_type:
                    param_strs = []
                    for param in parameters:
                        param_str = f"<{param.name}>"
                        if param.type and param.type != "Unknown":
                            param_str = f"<{param.name}> ({param.type})"
                        if not param.required:
                            param_str = f"[{param_str}]"
                        param_strs.append(param_str)
                    if param_strs:
                        signature = f"Новый {parent_type}({', '.join(param_strs)})"
                    else:
                        signature = f"Новый {parent_type}()"
            
            # Извлекаем информацию о версии
            since_version, _, _ = self._extract_version_info(content, soup)
            
            # Извлекаем примечания и доступность
            notes = self._extract_notes(content)
            availability = self._extract_availability(content)
            
            constructor = BslConstructor(
                signature=signature,
                parameters=parameters,
                description=description,
                examples=examples,
                since_version=since_version,
                notes=notes,
                availability=availability
            )
            
            # Сохраняем родительский тип (через setattr, так как это dataclass)
            constructor.parent_type = parent_type
            
            return constructor
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга конструктора из {file_path}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _parse_method_page(self, soup: BeautifulSoup, file_path: str) -> Optional[BslFunction]:
        """Парсит страницу метода объекта"""
        try:
            title = self._extract_title(soup)
            content = self._extract_content(soup)
            
            # Извлекаем родительский тип и имя метода из заголовка
            # Формат: "ДокументОбъект.Записать" или "ТипОбъекта.ИмяМетода (TypeObject.MethodName)"
            parent_type = None
            method_name = None
            
            if '.' in title:
                # Извлекаем русское имя метода (до скобок с английским)
                # Формат: "ДокументОбъект.<Имя документа>.Записать (DocumentObject.Write)"
                # Ищем последнюю часть до скобок
                title_before_brackets = re.split(r'\s*\(', title)[0]  # Часть до скобок
                parts = title_before_brackets.split('.')
                if len(parts) >= 2:
                    parent_type = parts[0].strip()
                    # Берем последнюю часть (имя метода)
                    method_part = parts[-1].strip()
                    # Убираем шаблоны типа <Имя документа>
                    method_name = re.sub(r'<[^>]+>\.?', '', method_part).strip()
            
            if not method_name:
                method_name = self._extract_function_name(title)
                # Если все еще содержит шаблоны, убираем их
                method_name = re.sub(r'<[^>]+>\.?', '', method_name).strip()
                # Убираем скобки с английским именем если остались
                method_name = re.split(r'\s*\(', method_name)[0].strip()
            
            # Извлекаем английское имя
            name_en = self._extract_english_name(title, content)
            
            # Извлекаем описание
            description = self._extract_description(content)
            
            # Извлекаем параметры (улучшенный парсинг для HTML структуры)
            parameters = self._extract_parameters_from_html(soup, content)
            
            # Извлекаем возвращаемое значение
            return_type, return_description = self._extract_return_value(content)
            
            # Извлекаем примеры (улучшенный парсинг для HTML структуры)
            examples = self._extract_examples_from_html(soup, content)
            
            # Извлекаем сигнатуру из HTML (класс V8SH)
            signature = self._extract_signature_from_html(soup, method_name, content)
            
            # Если сигнатура неполная и есть параметры, строим полную сигнатуру
            if signature == method_name and parameters:
                param_strs = []
                for param in parameters:
                    param_str = f"<{param.name}>"
                    if param.type and param.type != "Unknown":
                        param_str = f"<{param.name}> ({param.type})"
                    if not param.required:
                        param_str = f"[{param_str}]"
                    param_strs.append(param_str)
                if param_strs:
                    signature = f"{method_name}({', '.join(param_strs)})"
            
            # Извлекаем информацию о версии
            since_version, deprecated, deprecated_since = self._extract_version_info(content, soup)
            
            # Определяем категорию
            category = "Method"
            
            # Извлекаем связи с другими API элементами
            related_elements = self._extract_related_elements(content, method_name)
            
            # Извлекаем примечания и доступность
            notes = self._extract_notes(content)
            availability = self._extract_availability(content)
            
            func = BslFunction(
                name=method_name,
                name_en=name_en,
                description=description,
                parameters=parameters,
                return_type=return_type,
                return_description=return_description,
                examples=examples,
                category=category,
                signature=signature,
                since_version=since_version,
                deprecated=deprecated,
                deprecated_since=deprecated_since,
                notes=notes,
                availability=availability,
                related_elements=related_elements,
                parent_type=parent_type  # Добавляем родительский тип для методов
            )
            
            return func
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга метода из {file_path}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _parse_object_page(self, soup: BeautifulSoup, file_path: str) -> Optional[BslObject]:
        """Парсит страницу объекта"""
        try:
            title = self._extract_title(soup)
            content = self._extract_content(soup)
            
            # Извлекаем имя объекта
            object_name = self._extract_object_name(title)
            
            # Извлекаем английское имя
            name_en = self._extract_english_name(title, content)
            
            # Извлекаем описание
            description = self._extract_description(content)
            
            # Извлекаем методы (теперь возвращает List[BslFunction])
            methods = self._extract_methods(content, soup)
            
            # Извлекаем свойства (теперь возвращает List[BslProperty])
            properties = self._extract_properties(content, soup)
            
            # Извлекаем конструкторы
            constructors = self._extract_constructors(content, soup)
            
            # Извлекаем базовые типы
            base_types = self._extract_base_types(content)
            
            # Извлекаем информацию о версии
            since_version, _, _ = self._extract_version_info(content, soup)
            
            # Определяем категорию
            category = self._extract_category(file_path, content)
            
            return BslObject(
                name=object_name,
                name_en=name_en,
                description=description,
                methods=methods,
                properties=properties,
                constructors=constructors,
                base_types=base_types,
                category=category,
                since_version=since_version
            )
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга объекта из {file_path}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _parse_property_page(self, soup: BeautifulSoup, file_path: str) -> Optional[BslProperty]:
        """Парсит страницу свойства объекта"""
        try:
            title = self._extract_title(soup)
            content = self._extract_content(soup)
            
            # Извлекаем имя свойства из заголовка
            # Формат: "ТипОбъекта.ИмяСвойства (Type.PropertyName)" или "ИмяСвойства"
            property_name = None
            parent_type = None
            
            # Сначала убираем английское имя в скобках, чтобы не мешало разбору
            title_without_en = re.sub(r'\s*\([^)]+\)', '', title).strip()
            
            if '.' in title_without_en:
                parts = title_without_en.split('.')
                if len(parts) >= 2:
                    parent_type = parts[0].strip()
                    property_name = parts[-1].strip()
            
            if not property_name:
                # Пытаемся извлечь из заголовка
                property_name = self._extract_function_name(title_without_en)
            
            # Если parent_type не найден в заголовке, пытаемся извлечь из пути
            if not parent_type and '/properties/' in file_path:
                path_before_properties = file_path.split('/properties/')[0]
                path_parts = path_before_properties.split('/')
                if path_parts:
                    potential_parent = path_parts[-1]
                    potential_parent = re.sub(r'\d+\.(html|htm)$', '', potential_parent).strip()
                    if potential_parent:
                        parent_type = potential_parent
            
            # Извлекаем английское имя
            name_en = self._extract_english_name(title, content)
            
            # Извлекаем тип свойства
            prop_type, read_only, write_only = self._extract_property_details_from_page(
                content, property_name, soup
            )
            
            # Извлекаем описание
            description = self._extract_description(content)
            
            # Извлекаем примечания и доступность
            notes = self._extract_notes(content)
            availability = self._extract_availability(content)
            
            # Извлекаем информацию о версии
            since_version, _, _ = self._extract_version_info(content, soup)
            
            return BslProperty(
                name=property_name or "Unknown",
                name_en=name_en,
                type=prop_type,
                description=description,
                read_only=read_only,
                write_only=write_only,
                since_version=since_version,
                notes=notes,
                availability=availability,
                parent_type=parent_type or ""
            )
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга свойства из {file_path}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _parse_enum_page(self, soup: BeautifulSoup, file_path: str) -> Optional[BslEnum]:
        """Парсит страницу перечисления"""
        try:
            title = self._extract_title(soup)
            content = self._extract_content(soup)
            
            # Извлекаем имя перечисления
            enum_name = self._extract_enum_name(title)
            
            # Извлекаем описание
            description = self._extract_description(content)
            
            # Извлекаем значения
            values = self._extract_enum_values(content)
            
            # Определяем категорию
            category = self._extract_category(file_path, content)
            
            return BslEnum(
                name=enum_name,
                description=description,
                values=values,
                category=category
            )
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга перечисления из {file_path}: {e}")
            return None
    
    def _parse_index_page(self, soup: BeautifulSoup, file_path: str) -> Dict[str, any]:
        """Парсит индексную страницу"""
        result = {
            'links': [],
            'sections': []
        }
        
        try:
            # Ищем ссылки
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                text = link.get_text().strip()
                if href and text:
                    result['links'].append({
                        'href': href,
                        'text': text
                    })
            
            # Ищем разделы
            headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            for header in headers:
                text = header.get_text().strip()
                if text:
                    result['sections'].append(text)
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга индексной страницы {file_path}: {e}")
        
        return result
    
    def _extract_function_name(self, title: str) -> str:
        """Извлекает имя функции из заголовка"""
        from html import unescape
        title = unescape(title)
        
        # Паттерн 1: "Глобальный контекст.СтрДлина (Global context.StrLen)" или "Тип.Метод"
        # Извлекаем имя после последней точки до пробела или скобки
        match = re.search(r'\.([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*)\s*(?:\(|$)', title)
        if match:
            return match.group(1)
        
        # Паттерн 2: "ИмяФункции(Параметры)" - функция с параметрами
        match = re.search(r'([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*)\s*\(', title)
        if match:
            return match.group(1)
        
        # Паттерн 3: Просто имя функции без контекста
        # Убираем лишние символы и слова
        name = re.sub(r'[^\w\s]', '', title)
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Берем последнее слово (имя функции обычно в конце)
        words = name.split()
        if words:
            return words[-1]
        
        return "UnknownFunction"
    
    def _extract_object_name(self, title: str) -> str:
        """Извлекает имя объекта из заголовка"""
        from html import unescape
        title = unescape(title)
        
        # Ищем паттерн типа "ДокументОбъект.<Имя документа>" или "ДокументОбъект"
        # Извлекаем имя до точки, скобки или пробела
        match = re.search(r'^([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*(?:Объект|Object)?)', title)
        if match:
            return match.group(1)
        
        # Fallback: убираем часть после точки/скобки и берем первое слово
        name = re.sub(r'\s*[.<\(].*$', '', title)
        name = re.sub(r'[^\w\s]', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name.split()[0] if name else "UnknownObject"
    
    def _extract_enum_name(self, title: str) -> str:
        """Извлекает имя перечисления из заголовка"""
        # Убираем лишние слова
        name = re.sub(r'(Перечисление|Enum|Enumeration)', '', title, flags=re.IGNORECASE)
        name = re.sub(r'[^\w\s]', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name.split()[0] if name else "UnknownEnum"
    
    def _extract_description(self, content: str) -> str:
        """Извлекает описание из содержимого"""
        # Ищем описание после ключевых слов
        patterns = [
            r'Описание:\s*(.+?)(?=\n\n|\n[A-ZА-Я]|$)',
            r'Description:\s*(.+?)(?=\n\n|\n[A-ZА-Я]|$)',
            r'Назначение:\s*(.+?)(?=\n\n|\n[A-ZА-Я]|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                desc = match.group(1).strip()
                if len(desc) > 10:  # Достаточно длинное описание
                    return desc
        
        # Если не найдено, берем первые несколько предложений
        sentences = re.split(r'[.!?]+', content)
        description = ""
        for sentence in sentences[:3]:
            sentence = sentence.strip()
            if len(sentence) > 20:
                description += sentence + ". "
        
        return description.strip()
    
    def _extract_notes(self, content: str) -> str:
        """Извлекает примечания из содержимого"""
        # Ищем секцию "Примечание:" или "Примечания:"
        # Структура: <p class="V8SH_chapter">Примечание:</p>текст или Примечание:</p>текст
        note_patterns = [
            r'<p\s+class="V8SH_chapter">Примечание:</p>\s*(.+?)(?=<p\s+class="V8SH_chapter"|</body>|$)',
            r'Примечание:\s*</p>\s*(.+?)(?=<p\s+class="V8SH_chapter"|</body>|$)',
            r'Примечание:\s*(.+?)(?=<p\s+class="V8SH_chapter"|</body>|$)',
            r'Примечания:\s*(.+?)(?=<p\s+class="V8SH_chapter"|</body>|$)',
            r'Note:\s*(.+?)(?=<p\s+class="V8SH_chapter"|</body>|$)',
        ]
        
        for pattern in note_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                note = match.group(1).strip()
                # Очищаем от HTML тегов
                note = re.sub(r'<[^>]+>', ' ', note)
                note = unescape(note)
                # Убираем лишние пробелы
                note = re.sub(r'\s+', ' ', note)
                note = note.strip()
                
                # Убираем "Методическая информация" и подобные фразы в конце
                note = re.sub(r'\s*Методическая\s+информация.*$', '', note, flags=re.IGNORECASE)
                note = re.sub(r'\s*Использование\s+в\s+версии:.*$', '', note, flags=re.IGNORECASE)
                
                if note and len(note) > 3:  # Минимальная длина
                    return note
        
        return ""
    
    def _extract_availability(self, content: str) -> str:
        """Извлекает информацию о доступности (сервер/клиент)"""
        # Ищем секцию "Доступность:"
        # Структура: Доступность: </p><p>Сервер.</p> или <p class="V8SH_chapter">Доступность:</p><p>...</p>
        # Важно: останавливаемся на следующей секции (Примечание, Использование в версии и т.д.)
        avail_patterns = [
            r'<p\s+class="V8SH_chapter">Доступность:</p>\s*(.+?)(?=<p\s+class="V8SH_chapter"|</body>|$)',
            r'Доступность:\s*</p>\s*(.+?)(?=<p\s+class="V8SH_chapter"|Примечание:|Использование\s+в\s+версии:|</body>|$)',
            r'Доступность:\s*(.+?)(?=<p\s+class="V8SH_chapter"|Примечание:|Использование\s+в\s+версии:|</body>|$)',
            r'Availability:\s*(.+?)(?=<p\s+class="V8SH_chapter"|Примечание:|Использование\s+в\s+версии:|</body>|$)',
        ]
        
        for pattern in avail_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                avail = match.group(1).strip()
                # Очищаем от HTML тегов
                avail = re.sub(r'<[^>]+>', ' ', avail)
                avail = unescape(avail)
                # Убираем лишние пробелы
                avail = re.sub(r'\s+', ' ', avail)
                avail = avail.strip()
                
                # Убираем текст, который попал из следующих секций
                # Останавливаемся на "Примечание:", "Использование в версии:" и т.д.
                avail = re.sub(r'\s*Примечание:.*$', '', avail, flags=re.IGNORECASE)
                avail = re.sub(r'\s*Использование\s+в\s+версии:.*$', '', avail, flags=re.IGNORECASE)
                avail = re.sub(r'\s*Методическая\s+информация.*$', '', avail, flags=re.IGNORECASE)
                
                # Убираем точку в конце, если она есть
                avail = re.sub(r'\.\s*$', '', avail)
                
                if avail and len(avail) > 2:  # Минимальная длина
                    return avail
        
        return ""
    
    def _extract_parameters(self, content: str) -> List[BslParameter]:
        """Извлекает параметры функции с детальной информацией"""
        parameters = []
        
        # Ищем секцию параметров
        param_patterns = [
            r'Параметры?:\s*(.+?)(?=\n\n|\n(?:Возвращаемое|Return|Пример|Example|Описание|Description)|$)',
            r'Parameters?:\s*(.+?)(?=\n\n|\n(?:Возвращаемое|Return|Пример|Example|Описание|Description)|$)'
        ]
        
        param_section = None
        for pattern in param_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                param_section = match.group(1)
                break
        
        if param_section:
            # Парсим параметры - ищем строки вида "ИмяПараметра (Тип) - Описание"
            # Также поддерживаем формат "<ИмяПараметра> (Тип) - Описание"
            param_lines = param_section.split('\n')
            current_param_desc = ""
            
            for line in param_lines:
                line = line.strip()
                if not line or len(line) < 3:
                    # Пустая строка может быть частью описания предыдущего параметра
                    if current_param_desc:
                        continue
                    else:
                        continue
                
                # Паттерн 1: "<ИмяПараметра> (Тип) - Описание" или "ИмяПараметра (Тип) - Описание"
                param_match = re.match(r'^<?([\wА-Яа-я]+)>?\s*(?:\(([^)]+)\))?\s*[-–:]?\s*(.+)?$', line)
                if param_match:
                    param_name = param_match.group(1).strip()
                    param_type = param_match.group(2).strip() if param_match.group(2) else "Unknown"
                    param_desc = param_match.group(3).strip() if param_match.group(3) else ""
                    
                    # Проверяем, обязательный ли параметр
                    required = True
                    default_value = None
                    
                    # Ищем маркеры обязательности
                    if 'необязательный' in param_desc.lower() or 'optional' in param_desc.lower():
                        required = False
                    
                    # Ищем значение по умолчанию
                    default_patterns = [
                        r'По умолчанию:\s*(.+?)(?:\.|$|;)',
                        r'Значение по умолчанию:\s*(.+?)(?:\.|$|;)',
                        r'Default:\s*(.+?)(?:\.|$|;)',
                        r'Default value:\s*(.+?)(?:\.|$|;)'
                    ]
                    for pattern in default_patterns:
                        default_match = re.search(pattern, param_desc, re.IGNORECASE)
                        if default_match:
                            default_value = default_match.group(1).strip()
                            required = False
                            break
                    
                    # Если описание содержит "Тип:" в начале, это может быть тип параметра
                    type_match = re.match(r'^Тип:\s*(.+?)(?:\.|$)', param_desc)
                    if type_match and param_type == "Unknown":
                        param_type = type_match.group(1).strip()
                        param_desc = param_desc[len(type_match.group(0)):].strip()
                    
                    parameters.append(BslParameter(
                        name=param_name,
                        type=param_type,
                        description=param_desc,
                        required=required,
                        default_value=default_value
                    ))
                    current_param_desc = ""
                else:
                    # Возможно, это продолжение описания предыдущего параметра
                    if parameters and current_param_desc == "":
                        # Проверяем, не является ли это частью описания
                        if not re.match(r'^[А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*\s*\(', line):
                            # Это продолжение описания
                            if parameters:
                                parameters[-1].description += " " + line
                    else:
                        current_param_desc = line
        
        return parameters
    
    def _extract_return_value(self, content: str) -> Tuple[str, str]:
        """Извлекает возвращаемое значение. Обрезает по границе следующей секции (Доступность, Пример, Описание)."""
        # Секции, после которых обрезаем — не включаем их текст в возвращаемое значение
        section_stops = [
            r'\n\s*Доступность\s*:', r'\n\s*Availability\s*:',
            r'\n\s*Пример\s*:', r'\n\s*Example\s*:',
            r'\n\s*Описание\s*:', r'\n\s*Description\s*:',
            r'\n\s*Использование в версии\s*:', r'\n\s*Методическая информация',
        ]
        stop_pattern = '|'.join(section_stops)

        return_patterns = [
            r'Возвращаемое значение:\s*(.+?)(?=\n\n|\n[A-ZА-Я]|$)',
            r'Return value:\s*(.+?)(?=\n\n|\n[A-ZА-Я]|$)',
            r'Возвращает:\s*(.+?)(?=\n\n|\n[A-ZА-Я]|$)'
        ]

        for pattern in return_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return_desc = match.group(1).strip()
                # Обрезаем по первой следующей секции
                stop_match = re.search(stop_pattern, return_desc, re.IGNORECASE)
                if stop_match:
                    return_desc = return_desc[:stop_match.start()].strip()
                if not return_desc:
                    return "Unknown", ""
                # Пытаемся извлечь тип: "Тип: Число." или "Word - description"
                type_match = re.search(r'Тип:\s*([^.]+?)(?:\.|$)', return_desc, re.IGNORECASE)
                if type_match:
                    rt = type_match.group(1).strip()
                    # Не считаем типом фразы про доступность
                    if rt and not re.search(r'клиент|сервер|соединение|мобильн|веб|толстый|тонкий|автономн', rt, re.IGNORECASE):
                        rest = return_desc[type_match.end():].strip()
                        return rt, rest if rest else ""
                type_match = re.search(r'(\w+)\s*[-–]\s*(.+)', return_desc)
                if type_match:
                    return type_match.group(1), type_match.group(2)
                return "Unknown", return_desc

        return "Unknown", ""
    
    def _extract_constructor_signature_from_html(self, soup: BeautifulSoup, content: str) -> str:
        """Извлекает сигнатуру конструктора из HTML структуры"""
        # Ищем элемент с классом V8SH_chapter содержащий "Синтаксис"
        syntax_heading = soup.find('p', class_='V8SH_chapter', string=lambda x: x and 'Синтаксис' in x)
        if syntax_heading:
            # Ищем следующий текстовый элемент после заголовка
            next_elem = syntax_heading.find_next_sibling()
            # Пропускаем пустые элементы
            while next_elem and (not next_elem.get_text().strip() or next_elem.name in ['br']):
                next_elem = next_elem.find_next_sibling()
            
            if next_elem:
                # Собираем все текстовые узлы между syntax_heading и следующим разделом V8SH_chapter
                text_parts = []
                current = syntax_heading.next_sibling
                
                while current:
                    # Останавливаемся на следующем разделе V8SH_chapter (Параметры, Описание и т.д.)
                    if hasattr(current, 'name'):
                        if current.name == 'p' and 'V8SH_chapter' in current.get('class', []):
                            # Это следующий раздел, останавливаемся
                            break
                        if current.name in ['hr', 'HR']:
                            # HR тоже разделитель
                            break
                    
                    # Берем только текстовые узлы (включая строковые узлы с HTML-сущностями)
                    if isinstance(current, str):
                        text_parts.append(current)
                    elif hasattr(current, 'string') and current.string:
                        text_parts.append(current.string)
                    
                    current = current.next_sibling
                
                # Объединяем все части
                signature = ''.join(text_parts).strip()
                
                # Если не нашли в текстовых узлах, берем из первого элемента
                if not signature:
                    signature = next_elem.get_text(separator=' ', strip=True)
                
                # Декодируем HTML-сущности (&lt; -> <, &gt; -> >)
                from html import unescape
                signature = unescape(signature)
                
                # Сначала обрезаем до закрывающей скобки, если она есть (ДО удаления тегов, чтобы сохранить параметры)
                if '(' in signature and ')' in signature:
                    bracket_end = signature.find(')') + 1
                    signature = signature[:bracket_end].strip()
                
                # Убираем HTML теги если остались (но сохраняем угловые скобки параметров)
                # Угловые скобки параметров имеют формат <ИмяПараметра>, не путать с HTML тегами
                # HTML теги обычно содержат атрибуты или закрывающие теги
                signature = re.sub(r'<[^>]+\s+[^>]*>', '', signature)  # Удаляем теги с атрибутами
                signature = re.sub(r'</[^>]+>', '', signature)  # Удаляем закрывающие теги
                # НЕ удаляем простые угловые скобки <Имя> - это параметры
                
                # Очищаем от лишних пробелов и переносов
                signature = re.sub(r'\s+', ' ', signature).strip()
                
                # Затем убираем текст после ключевых слов разделов (на случай если скобок нет)
                stop_words = ['Описание', 'Description', 'Параметры', 'Parameters', 
                             'Пример', 'Example', 'Возвращаемое значение', 'Return value',
                             'Использование в версии', 'Методическая информация']
                for stop_word in stop_words:
                    # Ищем с двоеточием и без
                    for pattern in [stop_word + ':', stop_word]:
                        if pattern in signature:
                            # Берем только часть до ключевого слова
                            idx = signature.find(pattern)
                            if idx > 0:
                                signature = signature[:idx].strip()
                                break
                    if any(sw in signature for sw in stop_words):
                        break
                
                # Если нет скобок, но есть "Новый", добавляем пустые скобки
                if '(' not in signature and signature and ('Новый' in signature or 'New' in signature):
                    match = re.search(r'(Новый|New)\s+([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*(?:Объект|Object)?)', signature, re.IGNORECASE)
                    if match:
                        signature = f"{match.group(1)} {match.group(2)}()"
                
                # Проверяем валидность
                if signature and ('Новый' in signature or 'New' in signature):
                    return signature
        
        # Fallback: ищем в тексте напрямую
        syntax_match = re.search(r'Синтаксис:\s*(.+?)(?=Описание|Параметры|Пример|Возвращаемое|Return|Description|Parameters|Example|$)', content, re.DOTALL | re.IGNORECASE)
        if syntax_match:
            signature = syntax_match.group(1).strip()
            signature = re.sub(r'\s+', ' ', signature)
            
            # Убираем текст после ключевых слов
            stop_words = ['Описание:', 'Description:', 'Параметры:', 'Parameters:', 
                         'Пример:', 'Example:', 'Возвращаемое значение:', 'Return value:']
            for stop_word in stop_words:
                if stop_word in signature:
                    signature = signature.split(stop_word)[0].strip()
                    break
            
            # Обрезаем до закрывающей скобки
            if '(' in signature and ')' in signature:
                bracket_end = signature.find(')') + 1
                signature = signature[:bracket_end].strip()
            
            if signature and ('Новый' in signature or 'New' in signature):
                return signature
        
        # Ищем паттерн "Новый Тип(...)" в тексте
        constructor_match = re.search(r'Новый\s+([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*(?:Объект|Object)?)\s*\([^)]*\)', content, re.IGNORECASE)
        if constructor_match:
            return constructor_match.group(0).strip()
        
        return ""
    
    def _extract_signature_from_html(self, soup: BeautifulSoup, method_name: str, content: str) -> str:
        """Извлекает сигнатуру метода из HTML структуры (класс V8SH)"""
        # Ищем элемент с классом V8SH_chapter содержащий "Синтаксис"
        syntax_heading = soup.find('p', class_='V8SH_chapter', string=lambda x: x and 'Синтаксис' in x)
        if syntax_heading:
            # Ищем следующий текстовый элемент после заголовка
            next_elem = syntax_heading.find_next_sibling()
            # Пропускаем пустые элементы
            while next_elem and (not next_elem.get_text().strip() or next_elem.name in ['br']):
                next_elem = next_elem.find_next_sibling()
            if next_elem:
                signature = next_elem.get_text().strip()
                # Очищаем от лишних пробелов и переносов
                signature = re.sub(r'\s+', ' ', signature)
                # Убираем текст после "Параметры:" или "Возвращаемое значение:" или "Описание:"
                signature = re.split(r'(?:Параметры?|Возвращаемое значение|Описание|Return|Description):', signature, flags=re.IGNORECASE)[0].strip()
                
                # Проверяем валидность сигнатуры
                # Не должна начинаться с ключевых слов
                invalid_starts = ['Параметры', 'Parameters', 'Возвращаемое', 'Return', 'Описание', 'Description', 'Пример', 'Example']
                if any(signature.startswith(inv) for inv in invalid_starts):
                    # Пробуем найти сигнатуру в следующем элементе
                    next_elem = next_elem.find_next_sibling()
                    while next_elem:
                        text = next_elem.get_text().strip()
                        if text and not any(text.startswith(inv) for inv in invalid_starts):
                            # Проверяем, что это похоже на сигнатуру (содержит имя метода и скобки)
                            if method_name in text and '(' in text:
                                signature = text
                                signature = re.split(r'(?:Параметры?|Возвращаемое значение|Описание|Return|Description):', signature, flags=re.IGNORECASE)[0].strip()
                                break
                        if next_elem.name == 'p' and 'V8SH_chapter' in next_elem.get('class', []):
                            # Следующий раздел, останавливаемся
                            break
                        next_elem = next_elem.find_next_sibling()
                
                # Если сигнатура валидна (содержит имя метода и скобки)
                if signature and method_name in signature and '(' in signature:
                    # Обрезаем до закрывающей скобки
                    if ')' in signature:
                        bracket_end = signature.find(')') + 1
                        signature = signature[:bracket_end]
                    return signature
                elif signature and method_name in signature:
                    # Метод без параметров - возвращаем имя метода со скобками
                    return f"{method_name}()"
        
        # Fallback: ищем в тексте напрямую
        syntax_match = re.search(r'Синтаксис:\s*(.+?)(?=Параметры|Возвращаемое значение|Описание|$)', content, re.DOTALL | re.IGNORECASE)
        if syntax_match:
            signature = syntax_match.group(1).strip()
            signature = re.sub(r'\s+', ' ', signature)
            # Убираем текст после ключевых слов
            signature = re.split(r'(?:Параметры?|Возвращаемое значение|Описание|Return|Description):', signature, flags=re.IGNORECASE)[0].strip()
            
            # Проверяем валидность
            invalid_starts = ['Параметры', 'Parameters', 'Возвращаемое', 'Return', 'Описание', 'Description']
            if not any(signature.startswith(inv) for inv in invalid_starts):
                if method_name in signature and '(' in signature:
                    if ')' in signature:
                        bracket_end = signature.find(')') + 1
                        signature = signature[:bracket_end]
                    return signature
                elif method_name in signature:
                    return f"{method_name}()"
        
        # Fallback к обычному извлечению
        signature = self._extract_signature(content, method_name)
        
        # Если сигнатура невалидна, возвращаем базовую
        if signature in ['Возвращаемое значение:', 'Описание:', 'Description:', 'Return value:'] or not signature:
            return f"{method_name}()"
        
        return signature
    
    def _extract_parameters_from_html(self, soup: BeautifulSoup, content: str) -> List[BslParameter]:
        """Извлекает параметры из HTML структуры (класс V8SH)"""
        parameters = []
        
        # Ищем заголовок "Параметры"
        params_heading = soup.find('p', class_='V8SH_chapter', string=lambda x: x and 'Параметры' in x)
        if params_heading:
            # Ищем все div с классом V8SH_rubric - это блоки параметров
            rubric_divs = params_heading.find_all_next('div', class_='V8SH_rubric')
            
            for rubric_div in rubric_divs:
                # Проверяем, не дошли ли до следующего раздела
                prev_chapter = rubric_div.find_previous('p', class_='V8SH_chapter')
                if prev_chapter and prev_chapter != params_heading:
                    chapter_text = prev_chapter.get_text().strip()
                    if any(word in chapter_text for word in ['Возвращаемое', 'Return', 'Пример', 'Example', 'Описание', 'Description']):
                        break
                
                text = rubric_div.get_text().strip()
                
                # Формат: "<ИмяПараметра> (обязательный)" или "<ИмяПараметра> (необязательный)"
                param_match = re.match(r'^<([\wА-Яа-я]+)>\s*(?:\(([^)]+)\))?', text)
                if param_match:
                    param_name = param_match.group(1).strip()
                    required_text = param_match.group(2) if param_match.group(2) else ""
                    required = 'необязательный' not in required_text.lower() and 'optional' not in required_text.lower()
                    
                    # Ищем тип параметра - это первая ссылка <a> после div
                    param_type = "Unknown"
                    next_elem = rubric_div.find_next_sibling()
                    while next_elem:
                        if next_elem.name == 'a':
                            type_text = next_elem.get_text().strip()
                            if type_text and len(type_text) < 100 and not type_text.startswith('<'):
                                param_type = type_text
                                break
                        elif next_elem.name == 'div' and 'V8SH_rubric' in next_elem.get('class', []):
                            # Следующий параметр, останавливаемся
                            break
                        elif next_elem.name == 'p' and 'V8SH_chapter' in next_elem.get('class', []):
                            # Следующий раздел, останавливаемся
                            break
                        next_elem = next_elem.find_next_sibling()
                    
                    # Ищем описание - текст после типа (до следующего параметра или раздела)
                    description = ""
                    current = rubric_div.find_next_sibling()
                    while current:
                        # Останавливаемся на следующем параметре или разделе
                        if current.name == 'div' and 'V8SH_rubric' in current.get('class', []):
                            break
                        if current.name == 'p' and 'V8SH_chapter' in current.get('class', []):
                            break
                        
                        current_text = current.get_text().strip()
                        # Пропускаем пустые элементы, <br> и ссылки (типы уже обработали)
                        if current_text and current.name != 'a' and len(current_text) > 5:
                            if description:
                                description += " " + current_text
                            else:
                                description = current_text
                        
                        current = current.find_next_sibling()
                    
                    parameters.append(BslParameter(
                        name=param_name,
                        type=param_type,
                        description=description,
                        required=required,
                        default_value=None
                    ))
        
        # Если не нашли через HTML, используем обычный метод
        if not parameters:
            parameters = self._extract_parameters(content)
        
        return parameters
    
    def _extract_version_info(self, content: str, soup: BeautifulSoup) -> Tuple[str, bool, str]:
        """
        Извлекает информацию о версии платформы
        
        Returns:
            Tuple[since_version, deprecated, deprecated_since]
        """
        since_version = ""
        deprecated = False
        deprecated_since = ""
        
        # Ищем информацию о версии в тексте
        version_patterns = [
            r'Доступен,?\s*начиная\s*с\s*версии\s*([\d.]+)',
            r'Available\s*since\s*version\s*([\d.]+)',
            r'С\s*версии\s*([\d.]+)',
            r'Since\s*version\s*([\d.]+)'
        ]
        
        for pattern in version_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                since_version = match.group(1).strip()
                break
        
        # Ищем информацию об устаревании
        deprecated_patterns = [
            r'Устарел[ао]?\s*(?:с\s*версии)?\s*([\d.]+)?',
            r'Deprecated\s*(?:since\s*version)?\s*([\d.]+)?',
            r'Не рекомендуется\s*(?:с\s*версии)?\s*([\d.]+)?'
        ]
        
        for pattern in deprecated_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                deprecated = True
                if match.group(1):
                    deprecated_since = match.group(1).strip()
                break
        
        return since_version, deprecated, deprecated_since
    
    def _extract_english_name(self, title: str, content: str) -> str:
        """Извлекает английское имя из заголовка или содержимого"""
        from html import unescape
        title = unescape(title)
        
        # Паттерн 1: "Глобальный контекст.СтрДлина (Global context.StrLen)"
        # Извлекаем имя после последней точки в скобках
        match = re.search(r'\([^)]*\.([A-Z][a-zA-Z0-9_]+)\)', title)
        if match:
            english_name = match.group(1)
            if len(english_name) > 2 and not english_name.isdigit():
                return english_name
        
        # Паттерн 2: "РусскоеИмя (EnglishName)" или "EnglishName (РусскоеИмя)"
        name_patterns = [
            r'\(([A-Z][a-zA-Z0-9_]+)\)',  # В скобках после русского имени
            r'([A-Z][a-zA-Z0-9_]+)\s*\(',  # Перед скобкой с русским именем
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, title)
            if match:
                english_name = match.group(1)
                # Проверяем, что это похоже на имя (не слишком короткое, не число)
                if len(english_name) > 2 and not english_name.isdigit():
                    return english_name
        
        return ""
    
    def _extract_signature(self, content: str, function_name: str) -> str:
        """Извлекает полную сигнатуру функции"""
        # Ищем сигнатуру в разных местах
        
        # 1. Ищем секцию синтаксиса
        syntax_patterns = [
            r'Синтаксис:\s*(.+?)(?=\n\n|\n(?:Параметры|Parameters|Описание|Description|Возвращаемое|Return)|$)',
            r'Syntax:\s*(.+?)(?=\n\n|\n(?:Параметры|Parameters|Описание|Description|Возвращаемое|Return)|$)',
            r'Сигнатура:\s*(.+?)(?=\n\n|\n(?:Параметры|Parameters|Описание|Description|Возвращаемое|Return)|$)',
            r'Signature:\s*(.+?)(?=\n\n|\n(?:Параметры|Parameters|Описание|Description|Возвращаемое|Return)|$)'
        ]
        
        for pattern in syntax_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                signature = match.group(1).strip()
                # Очищаем от лишних пробелов и переносов строк
                signature = re.sub(r'\s+', ' ', signature)
                # Убираем текст после "Параметры:" или "Возвращаемое значение:"
                signature = re.split(r'(?:Параметры|Parameters|Возвращаемое значение|Return value):', signature, flags=re.IGNORECASE)[0].strip()
                # Обрезаем до закрывающей скобки, если она есть
                if '(' in signature and ')' in signature:
                    bracket_end = signature.find(')') + 1
                    signature = signature[:bracket_end]
                if signature and len(signature) > len(function_name):
                    return signature
        
        # 2. Ищем паттерн "ИмяФункции(Параметры)" в начале описания или в тексте
        signature_patterns = [
            rf'^{re.escape(function_name)}\s*\([^)]*\)',  # В начале строки
            rf'{re.escape(function_name)}\s*\([^)]*\)',   # В любом месте
        ]
        
        for pattern in signature_patterns:
            signature_match = re.search(pattern, content, re.MULTILINE)
            if signature_match:
                signature = signature_match.group(0).strip()
                # Очищаем от лишних пробелов
                signature = re.sub(r'\s+', ' ', signature)
                # Обрезаем до закрывающей скобки
                if ')' in signature:
                    bracket_end = signature.find(')') + 1
                    signature = signature[:bracket_end]
                return signature
        
        # 3. Пытаемся построить из имени и параметров (если параметры найдены)
        # Это будет сделано позже, когда параметры будут извлечены
        return function_name
    
    def _extract_examples(self, content: str) -> List[str]:
        """Извлекает примеры использования"""
        examples = []
        
        # Ищем секцию примеров
        example_patterns = [
            r'Пример[ы]?:\s*(.+?)(?=\n\n|\n(?:[A-ZА-Я]|См\.|See|Использование|Usage)|$)',
            r'Example[s]?:\s*(.+?)(?=\n\n|\n(?:[A-ZА-Я]|См\.|See|Использование|Usage)|$)',
            r'Пример[ы]?\s*использования:\s*(.+?)(?=\n\n|\n(?:[A-ZА-Я]|См\.|See|Использование|Usage)|$)',
            r'Usage\s*example[s]?:\s*(.+?)(?=\n\n|\n(?:[A-ZА-Я]|См\.|See|Использование|Usage)|$)'
        ]
        
        for pattern in example_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                example_section = match.group(1)
                # Разделяем на отдельные примеры по пустым строкам или по паттернам кода
                # Ищем блоки кода (строки, начинающиеся с отступом или содержащие типичные конструкции BSL)
                example_lines = example_section.split('\n')
                current_example = ""
                in_code_block = False
                
                for line in example_lines:
                    line_stripped = line.strip()
                    
                    # Определяем, является ли строка частью кода
                    is_code_line = (
                        line_stripped and (
                            line_stripped.startswith(('Если', 'Если', 'Тогда', 'КонецЕсли', 'Для', 'Пока', 'Попытка', 'Исключение')) or
                            '=' in line_stripped or
                            '(' in line_stripped or
                            line_stripped.endswith(';') or
                            re.match(r'^\s*[А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*\s*\(', line_stripped) or
                            re.match(r'^\s*[А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*\s*=', line_stripped)
                        )
                    )
                    
                    if is_code_line:
                        if not in_code_block:
                            # Начало нового блока кода
                            if current_example.strip():
                                examples.append(current_example.strip())
                            current_example = line_stripped + "\n"
                            in_code_block = True
                        else:
                            # Продолжение блока кода
                            current_example += line_stripped + "\n"
                    else:
                        if in_code_block:
                            # Конец блока кода
                            if current_example.strip():
                                examples.append(current_example.strip())
                            current_example = ""
                            in_code_block = False
                        elif line_stripped:
                            # Текст между примерами
                            current_example += line_stripped + "\n"
                
                if current_example.strip():
                    examples.append(current_example.strip())
        
        # Если примеры не найдены через паттерны, ищем блоки кода напрямую
        if not examples:
            # Ищем строки, похожие на код BSL
            code_lines = []
            for line in content.split('\n'):
                line_stripped = line.strip()
                if line_stripped and (
                    '=' in line_stripped or
                    '(' in line_stripped or
                    line_stripped.endswith(';') or
                    re.match(r'^[А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*\s*\(', line_stripped)
                ):
                    code_lines.append(line_stripped)
            
            if code_lines:
                # Группируем строки кода в примеры
                current_example = []
                for line in code_lines:
                    if line.endswith(';') or 'КонецЕсли' in line or 'КонецЦикла' in line:
                        current_example.append(line)
                        if len(current_example) >= 2:  # Минимум 2 строки для примера
                            examples.append('\n'.join(current_example))
                        current_example = []
                    else:
                        current_example.append(line)
                
                if current_example and len(current_example) >= 2:
                    examples.append('\n'.join(current_example))
        
        # Очищаем примеры от лишнего текста
        cleaned_examples = []
        for example in examples:
            # Убираем текст до первого кода
            lines = example.split('\n')
            code_start = 0
            for i, line in enumerate(lines):
                if re.match(r'^[А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*\s*[=\(]', line.strip()):
                    code_start = i
                    break
            
            cleaned = '\n'.join(lines[code_start:]).strip()
            if cleaned and len(cleaned) > 10:  # Минимум 10 символов
                cleaned_examples.append(cleaned)
        
        return cleaned_examples[:5]  # Максимум 5 примеров
    
    def _extract_examples_from_html(self, soup: BeautifulSoup, content: str) -> List[str]:
        """Извлекает примеры из HTML структуры (класс V8SH)"""
        examples = []
        
        # Ищем заголовок "Пример" или "Примеры"
        example_headings = soup.find_all('p', class_='V8SH_chapter', string=lambda x: x and ('Пример' in x or 'Example' in x))
        
        for heading in example_headings:
            # Ищем блоки кода после заголовка
            current_elem = heading.find_next_sibling()
            current_example = []
            
            while current_elem:
                # Останавливаемся на следующем разделе
                if current_elem.name == 'p' and 'V8SH_chapter' in current_elem.get('class', []):
                    break
                
                text = current_elem.get_text().strip()
                
                # Проверяем, является ли это кодом
                is_code = (
                    text and (
                        '=' in text or
                        '(' in text or
                        text.endswith(';') or
                        re.match(r'^[А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*\s*[=\(]', text) or
                        text.startswith(('Если', 'Тогда', 'КонецЕсли', 'Для', 'Пока', 'Попытка', 'Исключение'))
                    )
                )
                
                if is_code:
                    current_example.append(text)
                elif current_example:
                    # Конец блока кода
                    if len(current_example) >= 1:
                        example_text = '\n'.join(current_example)
                        if len(example_text) > 10:
                            examples.append(example_text)
                    current_example = []
                
                current_elem = current_elem.find_next_sibling()
            
            # Добавляем последний пример
            if current_example and len(current_example) >= 1:
                example_text = '\n'.join(current_example)
                if len(example_text) > 10:
                    examples.append(example_text)
        
        # Если не нашли через HTML, используем обычный метод
        if not examples:
            examples = self._extract_examples(content)
        
        return examples[:5]  # Максимум 5 примеров
    
    def _extract_related_elements(self, content: str, current_name: str) -> List[str]:
        """
        Извлекает упоминания других API элементов в описании и секции "См. также"
        
        Ищет паттерны типа "Тип.Метод", "Тип.Свойство", "Функция()" и т.д.
        Также извлекает ссылки из секции "См. также"
        """
        related = []
        
        # Сначала извлекаем из секции "См. также"
        see_also_patterns = [
            r'См\.\s*также:\s*(.+?)(?=\n\n|\n(?:[А-ЯA-Z]|$))',
            r'See\s*also:\s*(.+?)(?=\n\n|\n(?:[А-ЯA-Z]|$))',
            r'<p\s+class="V8SH_chapter">См\.\s*также:</p>\s*(.+?)(?=<p\s+class="V8SH_chapter"|$)',
        ]
        
        see_also_section = None
        for pattern in see_also_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                see_also_section = match.group(1)
                break
        
        if see_also_section:
            # Извлекаем ссылки из секции "См. также"
            # Паттерн: <a href="v8help://...">ИмяЭлемента</a>
            link_pattern = r'<a[^>]*href="[^"]*">([^<]+)</a>'
            for match in re.finditer(link_pattern, see_also_section):
                element_name = match.group(1).strip()
                if element_name and element_name not in related:
                    related.append(element_name)
        
        # Также ищем упоминания в описании (существующая логика)
        patterns = [
            # Тип.Метод или Тип.Свойство
            r'([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*(?:Объект|Object)?)\.([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*)',
            # Функция() или Метод()
            r'([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*)\s*\(',
            # Перечисление.Значение
            r'([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*)\.([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                if len(match.groups()) == 2:
                    # Тип.Метод или Тип.Свойство
                    type_name = match.group(1)
                    member_name = match.group(2)
                    full_name = f"{type_name}.{member_name}"
                    if full_name != current_name and full_name not in related:
                        related.append(full_name)
                elif len(match.groups()) == 1:
                    # Функция()
                    func_name = match.group(1)
                    if func_name != current_name and func_name not in related:
                        # Проверяем, что это похоже на имя функции/метода
                        if len(func_name) > 2 and func_name[0].isupper():
                            related.append(func_name)
        
        return related[:10]  # Максимум 10 связей
    
    def _extract_methods(self, content: str, soup: BeautifulSoup) -> List[BslFunction]:
        """Извлекает методы объекта с детальной информацией"""
        methods = []
        method_names_found = set()  # Для избежания дубликатов
        
        # Стратегия 1: Ищем методы, описанные прямо на странице объекта
        # Ищем секции с описанием методов (не только ссылки)
        method_sections = soup.find_all(['div', 'section', 'p'], class_=re.compile(r'method', re.I))
        
        # Также ищем по текстовым паттернам
        method_text_patterns = [
            r'Метод\s+([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*)\s*\([^)]*\)',
            r'([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*)\s*\([^)]*\)\s*[-–]',  # ИмяМетода(параметры) - описание
        ]
        
        for pattern in method_text_patterns:
            for match in re.finditer(pattern, content):
                method_name = match.group(1)
                if method_name not in method_names_found:
                    method_names_found.add(method_name)
                    # Пытаемся найти описание метода на странице
                    method_desc, method_params, method_sig = self._extract_method_details_from_page(
                        content, method_name, soup
                    )
                    
                    methods.append(BslFunction(
                        name=method_name,
                        name_en="",
                        description=method_desc,
                        parameters=method_params,
                        return_type="Unknown",
                        return_description="",
                        examples=[],
                        category="Method",
                        signature=method_sig if method_sig else method_name
                    ))
        
        # Стратегия 2: Ищем ссылки на методы (отдельные страницы)
        method_links = soup.find_all('a', href=re.compile(r'methods/'))
        if method_links:
            for link in method_links:
                link_text = link.get_text().strip()
                if not link_text:
                    continue
                
                # Паттерн: "ИмяМетода (EnglishName)" или "ИмяМетода"
                method_match = re.match(r'^([\wА-Яа-я]+)\s*(?:\(([A-Z][a-zA-Z0-9_]+)\))?', link_text)
                if method_match:
                    method_name = method_match.group(1).strip()
                    name_en = method_match.group(2) if method_match.group(2) else ""
                    
                    if method_name not in method_names_found:
                        method_names_found.add(method_name)
                        # Пытаемся найти описание метода на текущей странице
                        method_desc, method_params, method_sig = self._extract_method_details_from_page(
                            content, method_name, soup
                        )
                        
                        methods.append(BslFunction(
                            name=method_name,
                            name_en=name_en,
                            description=method_desc,
                            parameters=method_params,
                            return_type="Unknown",
                            return_description="",
                            examples=[],
                            category="Method",
                            signature=method_sig if method_sig else method_name
                        ))
        
        # Стратегия 3: Если не нашли через BeautifulSoup, пробуем через regex
        if not methods:
            method_patterns = [
                r'Методы?:\s*(.+?)(?=\n\n|\n(?:Свойства|Properties|События|Events|Конструкторы|Constructors)|$)',
                r'Methods?:\s*(.+?)(?=\n\n|\n(?:Свойства|Properties|События|Events|Конструкторы|Constructors)|$)'
            ]
            
            method_section = None
            for pattern in method_patterns:
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if match:
                    method_section = match.group(1)
                    break
            
            if method_section:
                # Парсим HTML-ссылки в секции методов
                # Паттерн: <a href="...">ИмяМетода (EnglishName)</a>
                link_pattern = r'<a[^>]*>([\wА-Яа-я]+)\s*(?:\(([A-Z][a-zA-Z0-9_]+)\))?</a>'
                for match in re.finditer(link_pattern, method_section):
                    method_name = match.group(1).strip()
                    name_en = match.group(2) if match.group(2) else ""
                    
                    if method_name not in method_names_found:
                        method_names_found.add(method_name)
                        method_desc, method_params, method_sig = self._extract_method_details_from_page(
                            content, method_name, soup
                        )
                        
                        methods.append(BslFunction(
                            name=method_name,
                            name_en=name_en,
                            description=method_desc,
                            parameters=method_params,
                            return_type="Unknown",
                            return_description="",
                            examples=[],
                            category="Method",
                            signature=method_sig if method_sig else method_name
                        ))
        
        return methods
    
    def _extract_constructor_details_from_page(self, content: str, constructor_name: str, soup: BeautifulSoup) -> Tuple[str, List[BslParameter], str]:
        """
        Извлекает детальную информацию о конструкторе со страницы объекта
        
        Returns:
            Tuple[description, parameters, signature]
        """
        description = ""
        parameters = []
        signature = ""
        
        # Ищем блок с описанием конструктора на странице
        constructor_patterns = [
            rf'Конструктор\s+{re.escape(constructor_name)}\s*[:\-]?\s*(.+?)(?=\n\n|\n(?:Метод|Свойство|Property|Параметры|Parameters)|$)',
            rf'{re.escape(constructor_name)}\s*\([^)]*\)\s*[-–:]\s*(.+?)(?=\n\n|\n(?:Метод|Свойство|Property|Параметры|Parameters)|$)',
        ]
        
        for pattern in constructor_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                constructor_block = match.group(1)
                # Извлекаем описание
                desc_match = re.search(r'^(.+?)(?:\n|Параметры|Parameters|Пример|Example)', constructor_block, re.DOTALL | re.IGNORECASE)
                if desc_match:
                    description = desc_match.group(1).strip()
                
                # Извлекаем параметры из блока конструктора
                params = self._extract_parameters(constructor_block)
                if params:
                    parameters = params
                
                # Извлекаем сигнатуру
                sig_match = re.search(r'Новый\s+[А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*(?:Объект|Object)?\s*\([^)]*\)', constructor_block, re.IGNORECASE)
                if sig_match:
                    signature = sig_match.group(0).strip()
                
                break
        
        # Если не нашли в специальном блоке, ищем сигнатуру в общем тексте
        if not signature:
            sig_patterns = [
                r'Новый\s+[А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*(?:Объект|Object)?\s*\([^)]*\)',
            ]
            for pattern in sig_patterns:
                sig_match = re.search(pattern, content, re.IGNORECASE)
                if sig_match:
                    signature = sig_match.group(0).strip()
                    # Очищаем от лишних символов
                    signature = re.sub(r'\s+', ' ', signature)
                    break
        
        return description, parameters, signature
    
    def _extract_method_details_from_page(self, content: str, method_name: str, soup: BeautifulSoup) -> Tuple[str, List[BslParameter], str]:
        """
        Извлекает детальную информацию о методе со страницы объекта
        
        Returns:
            Tuple[description, parameters, signature]
        """
        description = ""
        parameters = []
        signature = method_name
        
        # Ищем блок с описанием метода на странице
        # Паттерн: "Метод ИмяМетода" или "ИмяМетода(" с последующим описанием
        method_patterns = [
            rf'Метод\s+{re.escape(method_name)}\s*[:\-]?\s*(.+?)(?=\n\n|\n(?:Метод|Свойство|Property|Параметры|Parameters)|$)',
            rf'{re.escape(method_name)}\s*\([^)]*\)\s*[-–:]\s*(.+?)(?=\n\n|\n(?:Метод|Свойство|Property|Параметры|Parameters)|$)',
            rf'{re.escape(method_name)}\s*[-–:]\s*(.+?)(?=\n\n|\n(?:Метод|Свойство|Property|Параметры|Parameters)|$)',
        ]
        
        for pattern in method_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                method_block = match.group(1)
                # Извлекаем описание
                desc_match = re.search(r'^(.+?)(?:\n|Параметры|Parameters|Возвращаемое|Return|Пример|Example)', method_block, re.DOTALL | re.IGNORECASE)
                if desc_match:
                    description = desc_match.group(1).strip()
                
                # Извлекаем параметры из блока метода
                params = self._extract_parameters(method_block)
                if params:
                    parameters = params
                
                # Извлекаем сигнатуру
                sig_match = re.search(rf'{re.escape(method_name)}\s*\([^)]*\)', method_block)
                if sig_match:
                    signature = sig_match.group(0).strip()
                
                break
        
        # Если не нашли в специальном блоке, ищем сигнатуру в общем тексте
        if signature == method_name:
            sig_patterns = [
                rf'{re.escape(method_name)}\s*\([^)]*\)',
                rf'{re.escape(method_name)}\s*\([^)]*\)\s*[-–]',
            ]
            for pattern in sig_patterns:
                sig_match = re.search(pattern, content)
                if sig_match:
                    signature = sig_match.group(0).strip()
                    # Очищаем от лишних символов
                    signature = re.sub(r'\s+', ' ', signature)
                    if signature.endswith('-') or signature.endswith('–'):
                        signature = signature[:-1].strip()
                    break
        
        return description, parameters, signature
    
    def _extract_property_details_from_page(self, content: str, prop_name: str, soup: BeautifulSoup) -> Tuple[str, bool, bool]:
        """
        Извлекает детальную информацию о свойстве со страницы объекта
        
        Returns:
            Tuple[property_type, read_only, write_only]
        """
        prop_type = "Unknown"
        read_only = False
        write_only = False
        
        # Ищем блок с описанием свойства на странице
        # Паттерн: имя свойства, затем секция "Тип:"
        prop_patterns = [
            rf'{re.escape(prop_name)}\s*(?:\([^)]+\))?\s*(.+?)(?=\n\n|\n(?:Метод|Свойство|Property|Событие|Event)|$)',
            rf'<a[^>]*>{re.escape(prop_name)}</a>\s*(.+?)(?=\n\n|\n(?:Метод|Свойство|Property|Событие|Event)|$)',
        ]
        
        for pattern in prop_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                prop_block = match.group(1)
                
                # Извлекаем тип из секции "Тип:" - только название типа, не описание
                # Паттерн 1: Тип: <a href="...">НазваниеТипа</a>
                type_match = re.search(r'Тип:\s*<a[^>]*>([^<]+)</a>', prop_block, re.IGNORECASE)
                if type_match:
                    prop_type = type_match.group(1).strip()
                    # Очищаем от лишних символов
                    prop_type = re.sub(r'\.\s*$', '', prop_type).strip()
                else:
                    # Паттерн 2: Тип: НазваниеТипа. (с точкой в конце)
                    type_match = re.search(r'Тип:\s*([^<\n.]+?)(?:\.|\.\s|<br|$)', prop_block, re.IGNORECASE)
                    if type_match:
                        prop_type = type_match.group(1).strip()
                
                # Извлекаем read-only флаг
                if re.search(r'Только\s*чтение|Read-only|readonly', prop_block, re.IGNORECASE):
                    read_only = True
                
                # Извлекаем write-only флаг
                if re.search(r'Только\s*запись|Write-only|writeonly', prop_block, re.IGNORECASE):
                    write_only = True
                
                break
        
        # Если не нашли в блоке, ищем в общем содержимом (для страниц свойств)
        if prop_type == "Unknown":
            # Ищем секцию "Тип:" в общем содержимом
            type_match = re.search(r'<p\s+class="V8SH_chapter">Тип:</p>\s*<a[^>]*>([^<]+)</a>', content, re.IGNORECASE)
            if not type_match:
                type_match = re.search(r'Тип:\s*<a[^>]*>([^<]+)</a>', content, re.IGNORECASE)
            if type_match:
                prop_type = type_match.group(1).strip()
                prop_type = re.sub(r'\.\s*$', '', prop_type).strip()
        
        return prop_type, read_only, write_only
    
    def _extract_properties(self, content: str, soup: BeautifulSoup) -> List[BslProperty]:
        """Извлекает свойства объекта с детальной информацией"""
        properties = []
        
        # Сначала пытаемся извлечь из HTML через BeautifulSoup
        prop_links = soup.find_all('a', href=re.compile(r'properties/'))
        if prop_links:
            for link in prop_links:
                link_text = link.get_text().strip()
                if not link_text:
                    continue
                
                # Паттерн: "ИмяСвойства (EnglishName)" или "ИмяСвойства"
                prop_match = re.match(r'^([\wА-Яа-я]+)\s*(?:\(([A-Z][a-zA-Z0-9_]+)\))?', link_text)
                if prop_match:
                    prop_name = prop_match.group(1).strip()
                    name_en = prop_match.group(2) if prop_match.group(2) else ""
                    
                    # Извлекаем детальную информацию о свойстве
                    prop_type, read_only, write_only = self._extract_property_details_from_page(
                        content, prop_name, soup
                    )
                    
                    properties.append(BslProperty(
                        name=prop_name,
                        name_en=name_en,
                        type=prop_type,
                        description="",
                        read_only=read_only,
                        write_only=write_only
                    ))
        
        # Если не нашли через BeautifulSoup, пробуем через regex
        if not properties:
            prop_patterns = [
                r'Свойства?:\s*(.+?)(?=\n\n|\n(?:Методы|Methods|События|Events|Конструкторы|Constructors)|$)',
                r'Properties?:\s*(.+?)(?=\n\n|\n(?:Методы|Methods|События|Events|Конструкторы|Constructors)|$)'
            ]
            
            prop_section = None
            for pattern in prop_patterns:
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if match:
                    prop_section = match.group(1)
                    break
            
            if prop_section:
                # Парсим HTML-ссылки в секции свойств
                # Паттерн: <a href="...">ИмяСвойства (EnglishName)</a>
                link_pattern = r'<a[^>]*>([\wА-Яа-я]+)\s*(?:\(([A-Z][a-zA-Z0-9_]+)\))?</a>'
                for match in re.finditer(link_pattern, prop_section):
                    prop_name = match.group(1).strip()
                    name_en = match.group(2) if match.group(2) else ""
                    
                    # Извлекаем детальную информацию о свойстве
                    prop_type, read_only, write_only = self._extract_property_details_from_page(
                        content, prop_name, soup
                    )
                    
                    # Извлекаем примечания и доступность для свойства
                    prop_block_pattern = rf'{re.escape(prop_name)}\s*(?:\([^)]+\))?\s*(.+?)(?=\n\n|\n(?:Метод|Свойство|Property|Событие|Event)|$)'
                    prop_block_match = re.search(prop_block_pattern, content, re.DOTALL | re.IGNORECASE)
                    prop_content = prop_block_match.group(1) if prop_block_match else content
                    
                    notes = self._extract_notes(prop_content)
                    availability = self._extract_availability(prop_content)
                    
                    properties.append(BslProperty(
                        name=prop_name,
                        name_en=name_en,
                        type=prop_type,
                        description="",
                        read_only=read_only,
                        write_only=write_only,
                        notes=notes,
                        availability=availability
                    ))
        
        return properties
    
    def _extract_constructors(self, content: str, soup: BeautifulSoup) -> List[BslConstructor]:
        """Извлекает конструкторы объекта из HTML структуры"""
        constructors = []
        
        # Стратегия 1: Ищем ссылки на страницы конструкторов
        constructor_links = soup.find_all('a', href=re.compile(r'constructors/'))
        if constructor_links:
            for link in constructor_links:
                link_text = link.get_text().strip()
                if not link_text:
                    continue
                
                # Пытаемся извлечь информацию о конструкторе из ссылки
                # Обычно это просто "Новый" или "New"
                constructor_name = link_text.strip()
                
                # Пытаемся найти описание конструктора на текущей странице
                constructor_desc, constructor_params, constructor_sig = self._extract_constructor_details_from_page(
                    content, constructor_name, soup
                )
                
                constructors.append(BslConstructor(
                    signature=constructor_sig if constructor_sig else f"Новый {constructor_name}()",
                    parameters=constructor_params,
                    description=constructor_desc
                ))
        
        # Стратегия 2: Ищем секцию конструкторов в тексте
        if not constructors:
            constructor_patterns = [
                r'Конструкторы?:\s*(.+?)(?=\n\n|\n(?:Методы|Methods|Свойства|Properties)|$)',
                r'Constructors?:\s*(.+?)(?=\n\n|\n(?:Методы|Methods|Свойства|Properties)|$)',
                r'Создание\s*объекта:\s*(.+?)(?=\n\n|\n(?:Методы|Methods|Свойства|Properties)|$)'
            ]
            
            constructor_section = None
            for pattern in constructor_patterns:
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if match:
                    constructor_section = match.group(1)
                    break
            
            if constructor_section:
                # Ищем заголовок "Конструкторы" в HTML
                constructor_heading = soup.find('p', class_='V8SH_chapter', string=lambda x: x and ('Конструктор' in x or 'Constructor' in x))
                if constructor_heading:
                    # Ищем блоки с описанием конструкторов после заголовка
                    current_elem = constructor_heading.find_next_sibling()
                    current_constructor = None
                    
                    while current_elem:
                        # Останавливаемся на следующем разделе
                        if current_elem.name == 'p' and 'V8SH_chapter' in current_elem.get('class', []):
                            if current_constructor:
                                constructors.append(current_constructor)
                            break
                        
                        text = current_elem.get_text().strip()
                        
                        # Ищем сигнатуру конструктора
                        constructor_match = re.search(r'Новый\s+([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*(?:Объект|Object)?)\s*\(([^)]*)\)', text, re.IGNORECASE)
                        if constructor_match:
                            if current_constructor:
                                constructors.append(current_constructor)
                            
                            type_name = constructor_match.group(1).strip()
                            params_str = constructor_match.group(2).strip() if constructor_match.group(2) else ""
                            
                            # Извлекаем параметры из HTML структуры
                            params = []
                            # Ищем параметры в следующих элементах
                            param_elem = current_elem.find_next_sibling()
                            while param_elem:
                                if param_elem.name == 'div' and 'V8SH_rubric' in param_elem.get('class', []):
                                    param_text = param_elem.get_text().strip()
                                    param_match = re.match(r'^<([\wА-Яа-я]+)>', param_text)
                                    if param_match:
                                        param_name = param_match.group(1)
                                        param_type = "Unknown"
                                        
                                        # Ищем тип параметра
                                        type_link = param_elem.find_next_sibling('a')
                                        if type_link:
                                            param_type = type_link.get_text().strip()
                                        
                                        params.append(BslParameter(
                                            name=param_name,
                                            type=param_type,
                                            description=""
                                        ))
                                elif param_elem.name == 'p' and 'V8SH_chapter' in param_elem.get('class', []):
                                    break
                                param_elem = param_elem.find_next_sibling()
                            
                            # Если параметры не найдены через HTML, парсим из строки
                            if not params and params_str:
                                param_names = [p.strip() for p in params_str.split(',') if p.strip()]
                                for param_name in param_names:
                                    params.append(BslParameter(
                                        name=param_name,
                                        type="Unknown",
                                        description=""
                                    ))
                            
                            # Извлекаем описание
                            desc_elem = current_elem.find_next_sibling()
                            description = ""
                            while desc_elem and desc_elem.name != 'div' and 'V8SH_rubric' not in desc_elem.get('class', []):
                                if desc_elem.name == 'p' and 'V8SH_chapter' in desc_elem.get('class', []):
                                    break
                                desc_text = desc_elem.get_text().strip()
                                if desc_text and len(desc_text) > 10:
                                    if description:
                                        description += " " + desc_text
                                    else:
                                        description = desc_text
                                desc_elem = desc_elem.find_next_sibling()
                            
                            current_constructor = BslConstructor(
                                signature=f"Новый {type_name}({params_str})" if params_str else f"Новый {type_name}()",
                                parameters=params,
                                description=description
                            )
                        
                        current_elem = current_elem.find_next_sibling()
                    
                    if current_constructor:
                        constructors.append(current_constructor)
                else:
                    # Fallback: парсим из текста (старая логика)
                    constructor_lines = constructor_section.split('\n')
                    current_constructor = None
                    
                    for line in constructor_lines:
                        line = line.strip()
                        if not line:
                            if current_constructor:
                                constructors.append(current_constructor)
                                current_constructor = None
                            continue
                        
                        # Паттерн: "Новый Тип(Параметры)" или "New Type(Parameters)"
                        constructor_match = re.match(r'^(?:Новый|New)\s+([\wА-Яа-я.]+)\s*\(([^)]*)\)', line, re.IGNORECASE)
                        if constructor_match:
                            if current_constructor:
                                constructors.append(current_constructor)
                            
                            type_name = constructor_match.group(1).strip()
                            params_str = constructor_match.group(2).strip()
                            
                            # Парсим параметры
                            parameters = []
                            if params_str:
                                param_names = [p.strip() for p in params_str.split(',') if p.strip()]
                                for param_name in param_names:
                                    parameters.append(BslParameter(
                                        name=param_name,
                                        type="Unknown",
                                        description=""
                                    ))
                            
                            current_constructor = BslConstructor(
                                signature=line,
                                parameters=parameters,
                                description=""
                            )
                        elif current_constructor and line:
                            # Добавляем описание к текущему конструктору
                            if not current_constructor.description:
                                current_constructor.description = line
                            else:
                                current_constructor.description += " " + line
                    
                    if current_constructor:
                        constructors.append(current_constructor)
        
        return constructors
    
    def _extract_base_types(self, content: str) -> List[str]:
        """Извлекает базовые типы (наследование)"""
        base_types = []
        
        # Ищем информацию о наследовании
        inheritance_patterns = [
            r'Наследует?:\s*([\wА-Яа-я.,\s]+)',
            r'Inherits?:\s*([\wА-Яа-я.,\s]+)',
            r'Базовый\s*тип:\s*([\wА-Яа-я.,\s]+)',
            r'Base\s*type:\s*([\wА-Яа-я.,\s]+)'
        ]
        
        for pattern in inheritance_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                types_str = match.group(1).strip()
                # Разделяем по запятым
                types = [t.strip() for t in types_str.split(',') if t.strip()]
                base_types.extend(types)
                break
        
        return base_types
    
    def _extract_enum_values(self, content: str) -> List[Dict[str, str]]:
        """Извлекает значения перечисления"""
        values = []
        
        # Ищем секцию значений
        value_patterns = [
            r'Значения?:\s*(.+?)(?=\n\n|\n[A-ZА-Я]|$)',
            r'Элементы?:\s*(.+?)(?=\n\n|\n[A-ZА-Я]|$)',
            r'Values?:\s*(.+?)(?=\n\n|\n[A-ZА-Я]|$)'
        ]
        
        for pattern in value_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                value_section = match.group(1)
                # Парсим значения
                value_lines = value_section.split('\n')
                for line in value_lines:
                    line = line.strip()
                    if line and ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            value_name = parts[0].strip()
                            value_desc = parts[1].strip()
                            values.append({
                                'name': value_name,
                                'description': value_desc
                            })
        
        return values
    
    def _extract_category(self, file_path: str, content: str) -> str:
        """Определяет категорию по пути к файлу и содержимому"""
        if '/global-methods/' in file_path:
            return 'GlobalMethod'
        elif '/global-properties/' in file_path:
            return 'GlobalProperty'
        elif '/objects/' in file_path:
            return 'Object'
        elif '/enums/' in file_path:
            return 'Enum'
        elif '/constructors/' in file_path:
            return 'Constructor'
        else:
            return 'Unknown'

# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Тестируем парсер
    parser = HtmlParser()
    
    # Пример HTML содержимого
    sample_html = """
    <html>
    <head><title>СтрДлина</title></head>
    <body>
        <h1>СтрДлина</h1>
        <p>Описание: Возвращает количество символов в строке.</p>
        <p>Синтаксис: СтрДлина(Строка)</p>
        <p>Параметры:</p>
        <ul>
            <li>Строка - строка, для которой определяется количество символов</li>
        </ul>
        <p>Возвращаемое значение: Число - количество символов в строке</p>
        <p>Пример:</p>
        <pre>ДлинаСтроки = СтрДлина("Привет, мир!"); // 12</pre>
    </body>
    </html>
    """
    
    result = parser.parse_html_content(sample_html, "global-methods/StrLength.html")
    
    print(f"Тип страницы: {result['type']}")
    print(f"Заголовок: {result['title']}")
    
    if result['functions']:
        func = result['functions'][0]
        print(f"Функция: {func.name}")
        print(f"Описание: {func.description}")
        print(f"Параметры: {func.parameters}")
        print(f"Возвращает: {func.return_type} - {func.return_description}")
