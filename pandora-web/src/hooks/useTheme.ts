import { useLayoutEffect, useState } from 'react';
import { isThemeName, type ThemeName } from '../theme';

const THEME_STORAGE_KEY = 'pandora-theme';

function loadTheme(): ThemeName {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  return isThemeName(stored) ? stored : 'forest';
}

export function useTheme() {
  const [theme, setTheme] = useState<ThemeName>(loadTheme);

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  return { theme, setTheme };
}
