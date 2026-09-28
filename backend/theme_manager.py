"""主题管理器 - 管理主题状态、检测系统主题、保存用户偏好"""

import os
from typing import Optional


class ThemeManager:
    """主题管理器"""
    
    # 主题模式
    THEME_SYSTEM = "system"
    THEME_LIGHT = "light"
    THEME_DARK = "dark"
    
    def __init__(self, config_manager):
        """
        初始化主题管理器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        
        # 获取用户偏好主题
        self.user_theme = self.config_manager.get_theme()
        
        # 检测系统主题
        self.system_theme = self._detect_system_theme()
    
    def _detect_system_theme(self) -> str:
        """
        检测系统主题（使用 darkdetect 跨平台库）
        
        Returns:
            系统主题 ("light" 或 "dark")，检测失败返回 "light"
        """
        try:
            import darkdetect
            
            if darkdetect.isDark():
                return self.THEME_DARK
            else:
                return self.THEME_LIGHT
        except Exception:
            return self.THEME_LIGHT
    
    def get_effective_theme(self) -> str:
        """
        获取当前有效的主题（考虑用户偏好和系统主题）
        
        Returns:
            当前主题 ("light" 或 "dark")
        """
        if self.user_theme == self.THEME_SYSTEM:
            return self.system_theme
        return self.user_theme
    
    def set_user_theme(self, theme: str):
        """
        设置用户偏好主题
        
        Args:
            theme: 主题类型 ("system", "light", "dark")
        """
        if theme not in [self.THEME_SYSTEM, self.THEME_LIGHT, self.THEME_DARK]:
            raise ValueError(f"无效的主题类型: {theme}")
        
        self.user_theme = theme
        self.config_manager.set_theme(theme)
    
    def get_user_theme(self) -> str:
        """获取用户偏好主题"""
        return self.user_theme
    
    def get_system_theme(self) -> str:
        """获取系统主题"""
        return self.system_theme
    
    def refresh_system_theme(self):
        """刷新系统主题检测"""
        self.system_theme = self._detect_system_theme()
    
    def is_dark_mode(self) -> bool:
        """检查当前是否为深色模式"""
        return self.get_effective_theme() == self.THEME_DARK