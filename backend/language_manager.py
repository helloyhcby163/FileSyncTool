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
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

from .platform_utils import (
    get_resource_path,
    detect_system_language,
    get_default_config_dir,
)
from .file_utils import delete_dir_contents, rollback_copied_files

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

    def __init__(
        self,
        language: str = None,
        translations_dir: Optional[str] = None,
        user_translations_dir: Optional[str] = None,
    ):
        """
        初始化多语言管理器

        Args:
            language: 当前语言代码，为 None 时自动检测系统语言
            translations_dir: 内置翻译文件目录，为 None 时使用 get_resource_path 解析
            user_translations_dir: 用户外挂翻译目录，为 None 时使用
                用户配置目录下的 translations/。同名语言以用户目录为准；
                用户文件损坏时回退使用内置版本。
        """
        if translations_dir is None:
            # 使用 get_resource_path 兼容 PyInstaller 打包环境
            translations_dir = get_resource_path("translations")
        if user_translations_dir is None:
            user_translations_dir = get_default_config_dir() / "translations"

        self.translations_dir = Path(translations_dir)
        self.user_translations_dir = Path(user_translations_dir)

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

    def _collect_language_files(self) -> Dict[str, List[Tuple[Path, bool]]]:
        """
        收集内置与用户外挂目录下的全部语言文件。

        Returns:
            {语言代码: [(文件路径, 是否用户目录文件), ...]}，
            每个语言的列表中内置文件在前、用户文件在后（用户优先覆盖）。
        """
        candidates: Dict[str, List[Tuple[Path, bool]]] = {}
        seen_dirs = set()
        for lang_dir, is_user_dir in (
            (self.translations_dir, False),
            (self.user_translations_dir, True),
        ):
            try:
                resolved = lang_dir.resolve()
            except Exception:
                resolved = lang_dir
            if resolved in seen_dirs or not lang_dir.is_dir():
                continue
            seen_dirs.add(resolved)
            for file_path in sorted(lang_dir.glob("*.json")):
                if file_path.is_file():
                    candidates.setdefault(file_path.stem, []).append((file_path, is_user_dir))
        return candidates

    def _load_all_translations(self):
        """
        扫描内置与用户外挂 translations 目录，加载全部 *.json 语言文件。

        同名语言代码：按“优先级 用户目录 > 内置目录”做按键合并——
        用户文件中出现的键覆盖内置版本，用户文件未提供的键仍取内置；
        用户文件损坏但内置版本可用时，打印警告并继续使用内置版本；
        两个来源都不可用时才标注为“损坏”。
        """
        self.translations = {}
        self.metas = {}
        self.broken_languages = {}
        self._raw_metas = {}
        self._scanned_files = []

        candidates = self._collect_language_files()
        self._scanned_files = sorted(candidates.keys())

        for lang in self._scanned_files:
            loaded_texts: Optional[dict] = None
            loaded_meta: Optional[dict] = None
            broken_reason: Optional[str] = None

            for file_path, is_user_file in candidates[lang]:
                result = self._parse_language_file(file_path)
                if result[0] == "ok":
                    _, texts, raw_meta = result
                    if loaded_texts is None:
                        # 首个有效文件（通常是内置版本）作为基底
                        loaded_texts = dict(texts)
                    else:
                        # 用户文件按键覆盖：同键以用户文件为准，缺键保留基底
                        loaded_texts.update(texts)
                    loaded_meta = raw_meta
                    broken_reason = None
                else:
                    reason = result[1]
                    if is_user_file and loaded_texts is not None:
                        # 用户文件损坏：保留内置版本，仅警告
                        print(f"用户语言文件 {file_path} 已损坏: {reason}，继续使用内置版本")
                        broken_reason = None
                    else:
                        broken_reason = reason

            if loaded_texts is not None and broken_reason is None:
                self.translations[lang] = loaded_texts
                self._raw_metas[lang] = loaded_meta or {}
            else:
                self._mark_broken(lang, broken_reason or "文件无法加载")

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

    def _parse_language_file(self, file_path: Path) -> Tuple[str, ...]:
        """
        解析并校验单个语言文件（不写入实例状态）。

        Returns:
            ("ok", texts, raw_meta) 或 ("broken", 损坏原因)
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            return ("broken", f"JSON 解析失败: {e}")

        if not isinstance(data, dict):
            return ("broken", "顶层结构不是 JSON 对象")

        # 新格式（含 meta/texts 包裹）；旧格式为整个扁平 dict
        if TEXTS_KEY in data or META_KEY in data:
            texts = data.get(TEXTS_KEY)
            if not isinstance(texts, dict):
                return ("broken", f"缺少必要字段 {TEXTS_KEY} 或其值不是对象")
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
                return ("broken", "texts 中存在非字符串的键或值")

        return ("ok", texts, raw_meta)

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

    # ===================== v7.6: 外挂语言目录迁移 =====================

    def migrate_user_translations_dir(self, new_dir: str) -> Tuple[bool, str]:
        """
        将用户外挂语言目录迁移到新路径（复制而非移动）。

        流程：逐文件复制（保留元数据）→ 验证所有 .json 可正常解析
        → 切换内部目录并重新加载语言。
        失败时回滚：删除本次已复制的文件；若目录为本次新建则整目录删除；
        不留下"一半迁移"状态。

        Returns:
            (是否成功, 失败原因描述；成功时为空字符串)
        """
        try:
            new_path = Path(new_dir).resolve()
        except Exception as e:
            return (False, f"无效的目标路径: {e}")

        old_dir = self.user_translations_dir
        try:
            same = new_path == old_dir.resolve()
        except Exception:
            same = str(new_path) == str(old_dir)
        if same:
            return (True, "")

        created_new_dir = False
        try:
            if not new_path.exists():
                new_path.mkdir(parents=True, exist_ok=True)
                created_new_dir = True
            elif not new_path.is_dir():
                return (False, "目标路径已存在同名文件，无法用作语言目录")
        except Exception as e:
            return (False, f"无法创建目标目录: {e}")

        # 复制前记录新路径下已存在的文件/目录（回滚时跳过）
        preexisting_files: Set[str] = set()
        preexisting_dirs: Set[str] = set()
        try:
            for p in new_path.rglob("*"):
                if p.is_dir():
                    preexisting_dirs.add(str(p))
                else:
                    preexisting_files.add(str(p))
        except Exception:
            pass

        copied_files: List[str] = []
        try:
            if old_dir.is_dir():
                for src in old_dir.rglob("*"):
                    if not src.is_file():
                        continue
                    dst = new_path / src.relative_to(old_dir)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src), str(dst))
                    copied_files.append(str(dst))
        except Exception as e:
            rollback_copied_files(
                new_path, copied_files, preexisting_files, preexisting_dirs, created_new_dir
            )
            return (False, f"复制失败，已回滚: {e}")

        try:
            # 验证：新路径下所有 .json 均可正常解析
            for json_file in new_path.rglob("*.json"):
                with open(json_file, "r", encoding="utf-8") as f:
                    json.load(f)
        except Exception as e:
            rollback_copied_files(
                new_path, copied_files, preexisting_files, preexisting_dirs, created_new_dir
            )
            return (False, f"验证失败，已回滚: {e}")

        # 切换内部路径并重新加载语言
        self.user_translations_dir = new_path
        try:
            self.reload_translations()
        except Exception as e:
            # 重新加载失败不视为迁移失败（文件本身已验证），仅提示
            print(f"重新加载语言文件失败: {e}")

        print(f"✅ 外挂语言目录已迁移到: {self.user_translations_dir}")
        return (True, "")

    def cleanup_old_translations_dir(self, old_dir: str) -> Tuple[bool, str]:
        """
        删除旧外挂语言目录下的全部文件（迁移成功后由用户确认调用）。

        Returns:
            (是否完全成功, 失败摘要)
        """
        return delete_dir_contents(Path(old_dir), exclude_names=())


def ensure_user_translations_dir(
    user_dir: Optional[Path] = None,
    builtin_dir: Optional[Path] = None,
) -> Path:
    """
    v7.6: 确保用户外挂语言目录存在；目录为空时用内置语言文件填充。

    - 目录不存在：创建
    - 目录为空：复制内置 zh/en/zh_tw.json 与 docs/TRANSLATING.md 作为起步模板
    - 目录非空：不做任何操作（后续启动、版本升级均不覆盖，避免用户翻译丢失）

    Returns:
        外挂语言目录路径
    """
    if user_dir is None:
        user_dir = get_default_config_dir() / "translations"
    user_dir = Path(user_dir)

    try:
        if not user_dir.exists():
            user_dir.mkdir(parents=True, exist_ok=True)
        if any(user_dir.iterdir()):
            return user_dir  # 目录非空：不覆盖
    except Exception as e:
        print(f"初始化外挂语言目录失败: {e}")
        return user_dir

    if builtin_dir is None:
        builtin_dir = Path(get_resource_path("translations"))

    copied = 0
    try:
        if Path(builtin_dir).is_dir():
            for name in ("zh.json", "en.json", "zh_tw.json"):
                src = Path(builtin_dir) / name
                if not src.is_file():
                    continue
                shutil.copy2(str(src), str(user_dir / name))
                copied += 1
    except Exception as e:
        print(f"复制内置语言文件失败: {e}")

    # 同时复制翻译说明文档
    try:
        docs_file = Path(get_resource_path("docs")) / "TRANSLATING.md"
        if docs_file.is_file():
            shutil.copy2(str(docs_file), str(user_dir / "TRANSLATING.md"))
    except Exception as e:
        print(f"复制翻译说明文档失败: {e}")

    if copied:
        print(f"外挂语言目录初始化完成: {user_dir}（复制 {copied} 个语言文件）")
    return user_dir


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
