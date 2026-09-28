"""
文件同步工具 v7.5.1 - 多语言管理器

语言文件格式（v7.5.1 起，存放于 translations/*.json）：
{
  "meta": {
    "name": "中文",                    # 语言显示名
    "code": "zh",                     # 语言代码
    "font": "Microsoft YaHei",        # 推荐字体（字符串或跨平台候选列表）
    "font_size": 13                   # 默认字号
  },
  "texts": {                          # 翻译文本（扁平键值对）
    "app_title": "文件同步工具"
  }
}

向后兼容：旧的扁平键值 JSON（没有 meta/texts 包裹）仍可加载，
meta 自动补全——显示名与代码取文件名，字体/字号回退 en.json。

损坏判定：JSON 解析失败、顶层不是对象、新格式缺少 texts 或 texts 不是对象、
texts 中存在非字符串键值，都会被标注为“损坏”且不允许选择。

文本两级回退：当前语言 → zh.json → en.json → 调用方 default → 键名。
系统语言不支持：回退 en.json；en.json 不可用时回退 zh.json。
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .platform_utils import get_resource_path, detect_system_language

# 语言文件字段名
META_KEY = "meta"
TEXTS_KEY = "texts"
META_NAME = "name"
META_CODE = "code"
META_FONT = "font"
META_FONT_SIZE = "font_size"

# en.json 也缺失或无 meta 时的最终兜底
DEFAULT_FONT_SIZE = 13
DEFAULT_FONT_FAMILIES: List[str] = [
    "Segoe UI",
    "Helvetica Neue",
    "Ubuntu",
    "Cantarell",
    "Noto Sans CJK SC",
    "Microsoft YaHei",
    "PingFang SC",
    "DejaVu Sans",
    "Arial",
]

# 文本缺失时的两级回退顺序
TEXT_FALLBACK_LANGS = ("zh", "en")
# 初始语言不可用时的回退顺序
INITIAL_FALLBACK_LANGS = ("en", "zh")
# 已知语言在列表中的优先顺序，新增语言按文件名排序排在后面
PREFERRED_LANG_ORDER = ("zh", "en", "zh_tw")


# ===================== 跨平台字体解析 =====================

# 已安装字体族集合查询结果缓存（None 表示当前环境无法查询）
_available_families: Optional[set] = None
# 候选列表 -> 实际选用字体族 的缓存
_family_pick_cache: Dict[Tuple[str, ...], Optional[str]] = {}


def _get_available_families() -> Optional[set]:
    """查询系统已安装的字体族集合（需要已初始化 Tk）；失败返回 None"""
    global _available_families
    if _available_families is None:
        try:
            from tkinter import font as tkfont
            families = tkfont.families()
            if families:
                _available_families = set(families)
        except Exception:
            _available_families = None
    return _available_families


def pick_font_family(candidates: List[str]) -> Optional[str]:
    """
    按候选顺序返回系统中实际安装的第一个字体族。

    无法查询或候选均未安装时，返回第一个候选交给 Tk 的字体替换机制，
    候选列表为空时返回 None（由 CustomTkinter 使用其默认字体）。
    """
    candidates_tuple = tuple(candidates)
    if not candidates_tuple:
        return None
    if candidates_tuple in _family_pick_cache:
        return _family_pick_cache[candidates_tuple]

    available = _get_available_families()
    result: Optional[str] = None
    if available:
        for family in candidates_tuple:
            if family in available:
                result = family
                break
    if result is None:
        result = candidates_tuple[0]
    _family_pick_cache[candidates_tuple] = result
    return result


class LanguageManager:
    """多语言管理器：动态扫描语言文件、解析 meta、提供翻译与字体配置"""

    # 最近创建的实例，供模块级 get_font 在语言管理器创建前的极早期兜底使用
    _active_instance: Optional["LanguageManager"] = None

    def __init__(self, language: str = None, translations_dir: Optional[str] = None):
        """
        初始化多语言管理器

        Args:
            language: 当前语言代码，为 None 时自动检测系统语言
            translations_dir: 翻译文件目录，为 None 时使用 get_resource_path 解析
        """
        if translations_dir is None:
            # 使用 get_resource_path 兼容 PyInstaller 打包环境
            translations_dir = get_resource_path("translations")

        self.translations_dir = Path(translations_dir)

        # 语言代码 -> 翻译文本
        self.translations: Dict[str, dict] = {}
        # 语言代码 -> 补全后的 meta
        self.metas: Dict[str, dict] = {}
        # 损坏语言代码 -> 损坏原因
        self.broken_languages: Dict[str, str] = {}
        # 扫描到的文件名（不含扩展名），按文件名字母序
        self._scanned_files: List[str] = []
        # 第一轮解析出的原始 meta（第二遍补全用）
        self._raw_metas: Dict[str, dict] = {}

        # 加载目录下全部语言文件
        self._load_all_translations()

        # 未指定语言时自动检测系统语言；不可用时按 en -> zh 回退
        if language is None:
            language = detect_system_language()
        self.current_language = self._resolve_initial_language(language)

        LanguageManager._active_instance = self

    # ===================== 文件加载与解析 =====================

    def _load_all_translations(self):
        """扫描 translations 目录，加载全部 *.json 语言文件"""
        self.translations = {}
        self.metas = {}
        self.broken_languages = {}
        self._raw_metas = {}
        self._scanned_files = []

        if not self.translations_dir.is_dir():
            return

        for file_path in sorted(self.translations_dir.glob("*.json")):
            lang = file_path.stem
            self._scanned_files.append(lang)
            self._load_one(file_path)

        # 第二遍补全 meta：先构建 en 的 meta 作为字体/字号回退基准
        if "en" in self._raw_metas:
            self.metas["en"] = self._build_meta("en", self._raw_metas["en"])
        elif "en" in self.broken_languages:
            self.metas["en"] = self._build_default_meta("en")

        for lang in self._scanned_files:
            if lang == "en" and lang in self.metas:
                continue
            if lang in self.broken_languages:
                self.metas[lang] = self._build_default_meta(lang)
            else:
                self.metas[lang] = self._build_meta(lang, self._raw_metas.get(lang, {}))

    def _load_one(self, file_path: Path):
        """加载并校验单个语言文件"""
        lang = file_path.stem

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self._mark_broken(lang, f"JSON 解析失败: {e}")
            return

        if not isinstance(data, dict):
            self._mark_broken(lang, "顶层结构不是 JSON 对象")
            return

        # 新格式（含 meta/texts 包裹）；旧格式为整个扁平 dict
        if TEXTS_KEY in data or META_KEY in data:
            texts = data.get(TEXTS_KEY)
            if not isinstance(texts, dict):
                self._mark_broken(lang, f"缺少必要字段 {TEXTS_KEY} 或其值不是对象")
                return
            raw_meta = data.get(META_KEY)
            if not isinstance(raw_meta, dict):
                # meta 允许缺失：用文件名补全，字体回退 en.json
                raw_meta = {}
        else:
            # 向后兼容：旧扁平格式整体即为 texts，meta 自动补全
            texts = data
            raw_meta = {}

        # 校验翻译键值类型
        for key, value in texts.items():
            if not isinstance(key, str) or not isinstance(value, str):
                self._mark_broken(lang, "texts 中存在非字符串的键或值")
                return

        self.translations[lang] = texts
        self._raw_metas[lang] = raw_meta

    def _mark_broken(self, lang: str, reason: str):
        """标注一个语言文件已损坏"""
        print(f"语言文件 {lang}.json 已损坏: {reason}")
        self.broken_languages[lang] = reason
        self.translations[lang] = {}
        self._raw_metas[lang] = {}

    def _build_default_meta(self, lang: str) -> dict:
        """构造兜底 meta（文件名作为显示名与代码，内置字体与字号）"""
        return {
            META_NAME: lang,
            META_CODE: lang,
            META_FONT: list(DEFAULT_FONT_FAMILIES),
            META_FONT_SIZE: DEFAULT_FONT_SIZE,
        }

    def _build_meta(self, lang: str, raw_meta: dict) -> dict:
        """
        补全单个语言的 meta。

        显示名/代码缺失时取文件名；字体/字号缺失时回退 en.json，
        en.json 也没有时使用内置默认值。
        """
        name = raw_meta.get(META_NAME)
        name = name.strip() if isinstance(name, str) and name.strip() else lang

        code = raw_meta.get(META_CODE)
        code = code.strip() if isinstance(code, str) and code.strip() else lang

        raw_font = raw_meta.get(META_FONT)
        if isinstance(raw_font, str):
            fonts = [raw_font.strip()] if raw_font.strip() else []
        elif isinstance(raw_font, list):
            fonts = [f.strip() for f in raw_font if isinstance(f, str) and f.strip()]
        else:
            fonts = []

        raw_size = raw_meta.get(META_FONT_SIZE)
        size = raw_size if (
            isinstance(raw_size, int) and not isinstance(raw_size, bool) and raw_size > 0
        ) else None

        # 字体与字号回退 en.json 的 meta
        en_meta = self.metas.get("en")
        en_fonts = en_meta.get(META_FONT) if en_meta else None
        en_size = en_meta.get(META_FONT_SIZE) if en_meta else None
        if not fonts:
            fonts = list(en_fonts) if en_fonts else list(DEFAULT_FONT_FAMILIES)
        if size is None:
            size = en_size if isinstance(en_size, int) and en_size > 0 else DEFAULT_FONT_SIZE

        return {
            META_NAME: name,
            META_CODE: code,
            META_FONT: fonts,
            META_FONT_SIZE: int(size),
        }

    # ===================== 语言列表与选择 =====================

    def get_available_languages(self) -> List[str]:
        """获取可选择的语言代码列表（损坏文件除外，已知语言优先）"""
        available = [lang for lang in self._scanned_files if lang not in self.broken_languages]
        preferred = [lang for lang in PREFERRED_LANG_ORDER if lang in available]
        rest = sorted(lang for lang in available if lang not in PREFERRED_LANG_ORDER)
        return preferred + rest

    def is_language_available(self, language: str) -> bool:
        """某语言是否存在且文件未损坏"""
        return language in self.get_available_languages()

    def is_language_broken(self, language: str) -> bool:
        """某语言文件是否已损坏"""
        return language in self.broken_languages

    def get_broken_languages(self) -> Dict[str, str]:
        """获取损坏的语言文件（语言代码 -> 损坏原因）"""
        return dict(self.broken_languages)

    def get_language_options(self) -> List[Tuple[str, str, bool]]:
        """
        获取语言下拉选项：[(语言代码, 显示名, 是否损坏), ...]

        可用语言在前（按 get_available_languages 顺序），损坏文件置后
        （按文件名排序，显示“文件名（损坏）”）。
        """
        suffix = self.get_text("language_broken_suffix", "（损坏）")
        options = [
            (lang, self.get_language_name(lang), False)
            for lang in self.get_available_languages()
        ]
        for lang in sorted(self.broken_languages):
            options.append((lang, f"{lang}.json{suffix}", True))
        return options

    def _resolve_initial_language(self, requested: Optional[str]) -> str:
        """
        解析初始/配置中的语言代码：
        精确匹配 → 主语言代码匹配 → en → zh → 第一个可用语言。
        """
        available = self.get_available_languages()
        if not available:
            return (requested or "en") if requested else "en"

        candidate = (requested or "").strip().lower()
        if candidate in available:
            return candidate

        # 主语言代码匹配（如 zh_tw 文件缺失但 zh 可用、en_US 匹配 en）
        if candidate:
            base = candidate.split("_")[0]
            for lang in available:
                if lang == base or lang.split("_")[0] == base:
                    return lang

        # 系统语言不支持 → 英文；英文不可用 → 中文
        for fallback in INITIAL_FALLBACK_LANGS:
            if fallback in available:
                return fallback
        return available[0]

    def set_language(self, language: str) -> bool:
        """
        设置当前语言（损坏或不存在的语言不允许切换）

        Returns:
            是否切换成功
        """
        if not language or not isinstance(language, str):
            return False
        language = language.strip().lower()
        if language in self.broken_languages:
            print(f"语言文件已损坏，无法切换: {language} ({self.broken_languages[language]})")
            return False
        if language in self.translations:
            self.current_language = language
            return True
        print(f"不支持的语言: {language}")
        return False

    def get_language(self) -> str:
        """获取当前语言代码"""
        return self.current_language

    def get_language_name(self, language: str = None) -> str:
        """
        获取语言的显示名称（来自 meta.name；缺少 meta 时返回文件名/代码）

        Args:
            language: 语言代码，默认为当前语言
        """
        if language is None:
            language = self.current_language
        meta = self.metas.get(language)
        if meta:
            return meta.get(META_NAME, language)
        return language

    def get_next_language(self) -> str:
        """获取下一个可用语言（供首页语言按钮循环切换，自动跳过损坏文件）"""
        languages = self.get_available_languages()
        if not languages:
            return self.current_language
        try:
            current_index = languages.index(self.current_language)
        except ValueError:
            return languages[0]
        next_index = (current_index + 1) % len(languages)
        return languages[next_index]

    # ===================== 翻译文本 =====================

    def get_text(self, key: str, default: str = None) -> str:
        """
        获取翻译文本

        查找顺序：当前语言 → zh.json → en.json → default → 键名

        Args:
            key: 文本键名
            default: 全部语言都找不到时的默认文本
        """
        lang_translations = self.translations.get(self.current_language)
        if isinstance(lang_translations, dict) and key in lang_translations:
            return lang_translations[key]

        # 两级回退：先 zh，再 en
        for fallback_lang in TEXT_FALLBACK_LANGS:
            if fallback_lang == self.current_language:
                continue
            fallback_translations = self.translations.get(fallback_lang)
            if isinstance(fallback_translations, dict) and key in fallback_translations:
                return fallback_translations[key]

        return default if default is not None else key

    def get_all_texts(self) -> Dict[str, str]:
        """获取当前语言的全部翻译文本（不含回退）"""
        return dict(self.translations.get(self.current_language, {}))

    def reload_translations(self):
        """重新扫描并加载翻译文件，当前语言失效时重新解析"""
        current = self.current_language
        self._load_all_translations()
        self.current_language = self._resolve_initial_language(current)

    def format_text(self, key: str, **kwargs) -> str:
        """
        格式化翻译文本（支持 {name} 形式的变量替换）

        Args:
            key: 文本键名
            **kwargs: 要替换的变量
        """
        text = self.get_text(key)
        for var_name, var_value in kwargs.items():
            text = text.replace(f"{{{var_name}}}", str(var_value))
        return text

    # ===================== meta 与字体 =====================

    def get_meta(self, language: str = None) -> dict:
        """
        获取语言 meta（返回副本）。

        meta 缺失时用文件名作为显示名与代码，字体/字号回退 en.json/内置默认值。
        """
        if language is None:
            language = self.current_language
        meta = self.metas.get(language)
        if meta:
            return dict(meta)
        return self._build_default_meta(language or "en")

    def get_default_font_size(self, language: str = None) -> int:
        """获取语言 meta 中配置的默认字号"""
        size = self.get_meta(language).get(META_FONT_SIZE, DEFAULT_FONT_SIZE)
        try:
            size = int(size)
            return size if size > 0 else DEFAULT_FONT_SIZE
        except (TypeError, ValueError):
            return DEFAULT_FONT_SIZE

    def get_font_family(self, language: str = None) -> Optional[str]:
        """
        获取当前系统可用的推荐字体族（按 meta.font 候选顺序匹配）。

        meta 缺少字体配置时回退 en.json，en.json 也没有时使用内置候选。
        """
        candidates = self.get_meta(language).get(META_FONT) or DEFAULT_FONT_FAMILIES
        return pick_font_family(candidates)

    def get_font(self, size: int = None, weight: str = "normal", **kwargs):
        """
        依据当前语言 meta 的推荐字体构造 CTkFont。

        Args:
            size: 字号，为 None 时使用 meta.font_size
            weight: 字重（normal/bold）
            **kwargs: 其它 CTkFont 参数（slant/underline/overstrike 等）

        Returns:
            customtkinter.CTkFont 实例
        """
        import customtkinter as ctk

        font_kwargs = {}
        family = self.get_font_family()
        if family:
            font_kwargs["family"] = family
        font_kwargs["size"] = int(size) if size is not None else self.get_default_font_size()
        if weight:
            font_kwargs["weight"] = weight
        font_kwargs.update(kwargs)
        return ctk.CTkFont(**font_kwargs)


def get_font(size: int = None, weight: str = "normal", **kwargs):
    """
    模块级字体工厂：使用最近创建的 LanguageManager 当前语言 meta 构造字体。

    供 GUI 控件统一调用；语言管理器尚未创建的启动极早期（如状态栏）
    自动使用内置默认字体，语言加载后可再用实例方法重配。
    """
    instance = LanguageManager._active_instance
    if instance is not None:
        return instance.get_font(size=size, weight=weight, **kwargs)

    import customtkinter as ctk

    font_kwargs = {}
    family = pick_font_family(DEFAULT_FONT_FAMILIES)
    if family:
        font_kwargs["family"] = family
    font_kwargs["size"] = int(size) if size is not None else DEFAULT_FONT_SIZE
    if weight:
        font_kwargs["weight"] = weight
    font_kwargs.update(kwargs)
    return ctk.CTkFont(**font_kwargs)
