"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Модуль для нормализации API элементов из справки 1С
"""

import hashlib
import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

from ..parsers.html_parser import BslFunction, BslObject, BslProperty, BslConstructor, BslParameter

logger = logging.getLogger(__name__)


class ApiElementType(str, Enum):
    """Тип элемента API"""
    TYPE = "type"
    METHOD = "method"
    PROPERTY = "property"
    CONSTRUCTOR = "constructor"
    ENUM = "enum"
    FUNCTION = "function"  # Глобальная функция


@dataclass
class ApiElement:
    """
    Нормализованный элемент API для индексации
    
    Представляет один элемент API (метод, свойство, тип, конструктор)
    с полной информацией для поиска и извлечения.
    """
    element_type: ApiElementType
    name: str  # Русское имя
    name_en: str = ""  # Английское имя
    full_name: str = ""  # Полное имя (Type.Method)
    parent_type: Optional[str] = None  # Родительский тип для методов/свойств
    description: str = ""
    platform_version: str = ""
    file_path: str = ""
    hbk_source: str = ""
    hbk_html_path: str = ""
    
    # Детальная информация в зависимости от типа
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Для поиска
    search_text: str = ""
    
    def __post_init__(self):
        """Инициализация после создания"""
        # Если full_name не задан, формируем его
        if not self.full_name:
            if self.parent_type:
                self.full_name = f"{self.parent_type}.{self.name}"
            else:
                self.full_name = self.name
        
        # Формируем текст для поиска
        if not self.search_text:
            self._build_search_text()
    
    def _build_search_text(self):
        """Формирует текст для поиска"""
        parts = [self.name]
        
        if self.name_en:
            parts.append(self.name_en)
        
        if self.full_name:
            parts.append(self.full_name)
        
        if self.description:
            parts.append(self.description)
        
        # Добавляем информацию из details
        if self.element_type == ApiElementType.METHOD:
            if 'signature' in self.details:
                parts.append(self.details['signature'])
            if 'parameters' in self.details:
                param_names = [p.get('name', '') for p in self.details['parameters']]
                parts.extend(param_names)
            if 'return_type' in self.details:
                parts.append(self.details['return_type'])
        
        self.search_text = " ".join(parts)
    
    def get_id(self) -> int:
        """
        Генерирует числовой ID для Qdrant
        
        Returns:
            uint64 ID
        """
        string_id = f"{self.platform_version}_{self.element_type.value}_{self.full_name}"
        return int(hashlib.md5(string_id.encode('utf-8')).hexdigest()[:15], 16) & 0x7FFFFFFFFFFFFFFF
    
    def get_original_id(self) -> str:
        """Возвращает строковый оригинальный ID"""
        return f"{self.platform_version}_{self.element_type.value}_{self.full_name}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует в словарь для сохранения в Qdrant"""
        return {
            'element_type': self.element_type.value,
            'name': self.name,
            'name_en': self.name_en,
            'full_name': self.full_name,
            'parent_type': self.parent_type,
            'description': self.description,
            'platform_version': self.platform_version,
            'file_path': self.file_path,
            'hbk_source': self.hbk_source,
            'hbk_html_path': self.hbk_html_path,
            'details': self.details,
            'search_text': self.search_text
        }


class ApiElementNormalizer:
    """Нормализует данные из парсера в список ApiElement"""
    
    @staticmethod
    def normalize_parsed_data(
        parsed_data: Dict[str, Any],
        platform_version: str,
        file_path: str,
        hbk_source: str,
        hbk_html_path: str
    ) -> List[ApiElement]:
        """
        Нормализует распарсенные данные в список ApiElement
        
        Args:
            parsed_data: Данные из HtmlParser.parse_html_content()
            platform_version: Версия платформы
            file_path: Путь к файлу
            hbk_source: Путь к HBK файлу
            hbk_html_path: Путь к HTML файлу внутри HBK
            
        Returns:
            Список нормализованных элементов API
        """
        elements = []
        page_type = parsed_data.get('type', 'unknown')
        
        # Обрабатываем функции
        for func in parsed_data.get('functions', []):
            # Проверяем, является ли это методом объекта (есть parent_type и это не функция глобального контекста)
            # Функции глобального контекста могут иметь parent_type="Глобальный контекст", но должны быть функциями
            is_global_function = (
                hasattr(func, 'parent_type') and 
                func.parent_type and 
                ('Глобальный контекст' in func.parent_type or 'Global context' in func.parent_type)
            )
            
            if hasattr(func, 'parent_type') and func.parent_type and not is_global_function:
                element = ApiElementNormalizer._method_to_element(
                    func, func.parent_type, platform_version, file_path, hbk_source, hbk_html_path
                )
            else:
                element = ApiElementNormalizer._function_to_element(
                    func, platform_version, file_path, hbk_source, hbk_html_path
                )
            if element:
                elements.append(element)
        
        # Обрабатываем объекты
        for obj in parsed_data.get('objects', []):
            # Создаем элемент для самого типа
            type_element = ApiElementNormalizer._object_to_type_element(
                obj, platform_version, file_path, hbk_source, hbk_html_path
            )
            if type_element:
                elements.append(type_element)
            
            # Создаем элементы для каждого метода
            for method in obj.methods:
                method_element = ApiElementNormalizer._method_to_element(
                    method, obj.name, platform_version, file_path, hbk_source, hbk_html_path
                )
                if method_element:
                    elements.append(method_element)
            
            # Создаем элементы для каждого свойства
            for prop in obj.properties:
                prop_element = ApiElementNormalizer._property_to_element(
                    prop, obj.name, platform_version, file_path, hbk_source, hbk_html_path
                )
                if prop_element:
                    elements.append(prop_element)
            
            # Создаем элементы для каждого конструктора
            for constructor in obj.constructors:
                constructor_element = ApiElementNormalizer._constructor_to_element(
                    constructor, obj.name, platform_version, file_path, hbk_source, hbk_html_path
                )
                if constructor_element:
                    elements.append(constructor_element)
        
        # Обрабатываем перечисления
        for enum in parsed_data.get('enums', []):
            element = ApiElementNormalizer._enum_to_element(
                enum, platform_version, file_path, hbk_source, hbk_html_path
            )
            if element:
                elements.append(element)
        
        # Обрабатываем конструкторы из отдельных страниц
        for constructor in parsed_data.get('constructors', []):
            # Извлекаем parent_type из конструктора
            parent_type = getattr(constructor, 'parent_type', None)
            if not parent_type:
                # Пытаемся извлечь из сигнатуры или пути
                if hasattr(constructor, 'signature') and constructor.signature:
                    # Формат: "Новый ТипОбъект(...)"
                    match = re.search(r'Новый\s+([А-Яа-яA-Za-z][А-Яа-яA-Za-z0-9]*(?:Объект|Object)?)', constructor.signature, re.IGNORECASE)
                    if match:
                        parent_type = match.group(1).strip()
            
            if parent_type:
                constructor_element = ApiElementNormalizer._constructor_to_element(
                    constructor, parent_type, platform_version, file_path, hbk_source, hbk_html_path
                )
                if constructor_element:
                    elements.append(constructor_element)
        
        # Обрабатываем свойства из отдельных страниц (page_type == 'property')
        for prop in parsed_data.get('properties', []):
            # Извлекаем parent_type из свойства
            # В _parse_property_page parent_type теперь сохраняется в prop.parent_type
            parent_type = getattr(prop, 'parent_type', None)
            
            # Если не нашли в свойстве, пытаемся извлечь из пути
            if not parent_type and '/properties/' in hbk_html_path:
                path_before_properties = hbk_html_path.split('/properties/')[0]
                path_parts = path_before_properties.split('/')
                if path_parts:
                    potential_parent = path_parts[-1]
                    # Убираем расширение и числа, если есть
                    potential_parent = re.sub(r'\d+\.(html|htm)$', '', potential_parent).strip()
                    if potential_parent:
                        parent_type = potential_parent
            
            if parent_type:
                prop_element = ApiElementNormalizer._property_to_element(
                    prop, parent_type, platform_version, file_path, hbk_source, hbk_html_path
                )
                if prop_element:
                    elements.append(prop_element)
        
        return elements
    
    @staticmethod
    def _function_to_element(
        func: BslFunction,
        platform_version: str,
        file_path: str,
        hbk_source: str,
        hbk_html_path: str
    ) -> Optional[ApiElement]:
        """Преобразует BslFunction в ApiElement"""
        return ApiElement(
            element_type=ApiElementType.FUNCTION,
            name=func.name,
            name_en=func.name_en,
            full_name=func.name,
            description=func.description,
            platform_version=platform_version,
            file_path=file_path,
            hbk_source=hbk_source,
            hbk_html_path=hbk_html_path,
            details={
                'signature': func.signature,
                'parameters': [
                    {
                        'name': p.name,
                        'type': p.type,
                        'description': p.description,
                        'required': p.required,
                        'default_value': p.default_value
                    }
                    for p in func.parameters
                ],
                'return_type': func.return_type,
                'return_description': func.return_description,
                'examples': func.examples,
                'since_version': func.since_version,
                'deprecated': func.deprecated,
                'deprecated_since': func.deprecated_since,
                'category': func.category,
                'notes': getattr(func, 'notes', ''),
                'availability': getattr(func, 'availability', ''),
                'related_elements': getattr(func, 'related_elements', [])  # Связи с другими элементами
            }
        )
    
    @staticmethod
    def _object_to_type_element(
        obj: BslObject,
        platform_version: str,
        file_path: str,
        hbk_source: str,
        hbk_html_path: str
    ) -> Optional[ApiElement]:
        """Преобразует BslObject в ApiElement типа TYPE"""
        return ApiElement(
            element_type=ApiElementType.TYPE,
            name=obj.name,
            name_en=obj.name_en,
            full_name=obj.name,
            description=obj.description,
            platform_version=platform_version,
            file_path=file_path,
            hbk_source=hbk_source,
            hbk_html_path=hbk_html_path,
            details={
                'base_types': obj.base_types,
                'methods': [m.name for m in obj.methods],
                'properties': [p.name for p in obj.properties],
                'constructors': [c.signature for c in obj.constructors],
                'since_version': obj.since_version,
                'category': obj.category
            }
        )
    
    @staticmethod
    def _method_to_element(
        method: BslFunction,
        parent_type: str,
        platform_version: str,
        file_path: str,
        hbk_source: str,
        hbk_html_path: str
    ) -> Optional[ApiElement]:
        """Преобразует метод объекта в ApiElement"""
        return ApiElement(
            element_type=ApiElementType.METHOD,
            name=method.name,
            name_en=method.name_en,
            full_name=f"{parent_type}.{method.name}",
            parent_type=parent_type,
            description=method.description,
            platform_version=platform_version,
            file_path=file_path,
            hbk_source=hbk_source,
            hbk_html_path=hbk_html_path,
            details={
                'signature': method.signature,
                'parameters': [
                    {
                        'name': p.name,
                        'type': p.type,
                        'description': p.description,
                        'required': p.required,
                        'default_value': p.default_value
                    }
                    for p in method.parameters
                ],
                'return_type': method.return_type,
                'return_description': method.return_description,
                'examples': method.examples,
                'notes': getattr(method, 'notes', ''),
                'availability': getattr(method, 'availability', ''),
                'related_elements': getattr(method, 'related_elements', []),
                'since_version': method.since_version,
                'deprecated': method.deprecated,
                'deprecated_since': method.deprecated_since
            }
        )
    
    @staticmethod
    def _property_to_element(
        prop: BslProperty,
        parent_type: str,
        platform_version: str,
        file_path: str,
        hbk_source: str,
        hbk_html_path: str
    ) -> Optional[ApiElement]:
        """Преобразует свойство объекта в ApiElement"""
        return ApiElement(
            element_type=ApiElementType.PROPERTY,
            name=prop.name,
            name_en=prop.name_en,
            full_name=f"{parent_type}.{prop.name}",
            parent_type=parent_type,
            description=prop.description,
            platform_version=platform_version,
            file_path=file_path,
            hbk_source=hbk_source,
            hbk_html_path=hbk_html_path,
            details={
                'type': prop.type,
                'read_only': prop.read_only,
                'write_only': prop.write_only,
                'notes': getattr(prop, 'notes', ''),
                'availability': getattr(prop, 'availability', ''),
                'related_elements': getattr(prop, 'related_elements', []),
                'since_version': prop.since_version
            }
        )
    
    @staticmethod
    def _constructor_to_element(
        constructor: BslConstructor,
        parent_type: str,
        platform_version: str,
        file_path: str,
        hbk_source: str,
        hbk_html_path: str
    ) -> Optional[ApiElement]:
        """Преобразует конструктор в ApiElement"""
        return ApiElement(
            element_type=ApiElementType.CONSTRUCTOR,
            name="Новый",
            name_en="New",
            full_name=f"Новый {parent_type}",
            parent_type=parent_type,
            description=constructor.description,
            platform_version=platform_version,
            file_path=file_path,
            hbk_source=hbk_source,
            hbk_html_path=hbk_html_path,
            details={
                'signature': constructor.signature,
                'parameters': [
                    {
                        'name': p.name,
                        'type': p.type,
                        'description': p.description,
                        'required': p.required,
                        'default_value': p.default_value
                    }
                    for p in constructor.parameters
                ],
                'examples': constructor.examples,
                'notes': getattr(constructor, 'notes', ''),
                'availability': getattr(constructor, 'availability', ''),
                'related_elements': getattr(constructor, 'related_elements', []),
                'since_version': constructor.since_version
            }
        )
    
    @staticmethod
    def _enum_to_element(
        enum,
        platform_version: str,
        file_path: str,
        hbk_source: str,
        hbk_html_path: str
    ) -> Optional[ApiElement]:
        """Преобразует перечисление в ApiElement"""
        return ApiElement(
            element_type=ApiElementType.ENUM,
            name=enum.name,
            full_name=enum.name,
            description=enum.description,
            platform_version=platform_version,
            file_path=file_path,
            hbk_source=hbk_source,
            hbk_html_path=hbk_html_path,
            details={
                'values': [
                    {
                        'name': v.get('name', ''),
                        'description': v.get('description', '')
                    }
                    for v in enum.values
                ],
                'category': enum.category
            }
        )

