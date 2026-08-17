"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Pydantic валидаторы для MCP tools
Обеспечивают проверку и санитизацию входных данных
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class SearchRequest(BaseModel):
    """Валидация запроса поиска"""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Поисковый запрос"
    )
    platform_version: Optional[str] = Field(
        None,
        pattern=r"^\d+\.\d+(\.\d+)?$",
        description="Версия платформы (формат: X.Y или X.Y.Z)"
    )
    limit: int = Field(
        10,
        ge=1,
        le=100,
        description="Количество результатов"
    )

    @field_validator('query')
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Санитизация поискового запроса"""
        # Удаляем потенциально опасные символы
        dangerous_chars = ['\x00', '\r', '\n']
        for char in dangerous_chars:
            v = v.replace(char, '')
        return v.strip()


class PlatformAPISearchRequest(BaseModel):
    """Валидация запроса поиска по API"""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Имя элемента или поисковый запрос"
    )
    element_type: Optional[Literal["function", "method", "property", "type", "constructor"]] = Field(
        None,
        description="Тип элемента API"
    )
    platform_version: Optional[str] = Field(
        None,
        pattern=r"^\d+\.\d+(\.\d+)?$",
        description="Версия платформы"
    )
    limit: int = Field(
        10,
        ge=1,
        le=100,
        description="Количество результатов"
    )

    @field_validator('query')
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Санитизация запроса"""
        return v.strip()


class GetElementRequest(BaseModel):
    """Валидация запроса получения элемента API"""

    model_config = ConfigDict(str_strip_whitespace=True)

    element_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Имя элемента"
    )
    element_type: Optional[Literal["function", "method", "property", "type", "constructor"]] = Field(
        None,
        description="Тип элемента"
    )
    parent_type: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Родительский тип (для методов/свойств)"
    )
    element_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="ID элемента"
    )
    platform_version: Optional[str] = Field(
        None,
        pattern=r"^\d+\.\d+(\.\d+)?$",
        description="Версия платформы"
    )

    @field_validator('element_name', 'parent_type', 'element_id')
    @classmethod
    def sanitize_strings(cls, v: Optional[str]) -> Optional[str]:
        """Санитизация строковых полей"""
        if v is None:
            return None
        return v.strip()


class GetTypeMembersRequest(BaseModel):
    """Валидация запроса получения членов типа"""

    model_config = ConfigDict(str_strip_whitespace=True)

    type_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Имя типа"
    )
    platform_version: Optional[str] = Field(
        None,
        pattern=r"^\d+\.\d+(\.\d+)?$",
        description="Версия платформы"
    )
    member_type: Optional[Literal["method", "property", "constructor"]] = Field(
        None,
        description="Тип члена"
    )
    include_constructors: bool = Field(
        True,
        description="Включить конструкторы"
    )

    @field_validator('type_name')
    @classmethod
    def sanitize_type_name(cls, v: str) -> str:
        """Санитизация имени типа"""
        return v.strip()


class ManageHelpRequest(BaseModel):
    """Валидация запроса управления справкой"""

    model_config = ConfigDict(str_strip_whitespace=True)

    action: Literal[
        "list", "list_versions", "list_indexed",
        "info", "version_info",
        "index", "reindex",
        "default_get", "default_set", "default_clear"
    ] = Field(
        ...,
        description="Действие"
    )
    version: Optional[str] = Field(
        None,
        pattern=r"^\d+\.\d+\.\d+$",  # Для default_set требуется полный формат
        description="Версия платформы (полный формат X.Y.Z)"
    )
    force: bool = Field(
        False,
        description="Принудительное выполнение"
    )
    show_indexed_only: bool = Field(
        False,
        description="Показать только проиндексированные"
    )

    @field_validator('version')
    @classmethod
    def sanitize_version(cls, v: Optional[str]) -> Optional[str]:
        """Санитизация версии"""
        if v is None:
            return None
        return v.strip()
