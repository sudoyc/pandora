import { Check, Palette } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { THEMES, type ThemeName } from '../theme';

type ThemeSwitcherProps = {
  theme: ThemeName;
  onThemeChange: (theme: ThemeName) => void;
  expanded?: boolean;
};

export function ThemeSwitcher({ theme, onThemeChange, expanded = false }: ThemeSwitcherProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const activeTheme = THEMES.find((option) => option.id === theme) ?? THEMES[0];

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  const options = (
    <div className="theme-options" role="group" aria-label="Available color themes">
      {THEMES.map((option) => (
        <button
          key={option.id}
          type="button"
          className="theme-option"
          aria-label={`Use ${option.label} theme`}
          aria-pressed={theme === option.id}
          onClick={() => {
            onThemeChange(option.id);
            setOpen(false);
          }}
        >
          <span className={`theme-swatch theme-swatch--${option.id}`} aria-hidden="true">
            <span /><span /><span />
          </span>
          <span>{option.label}</span>
          {theme === option.id && <Check size={16} aria-hidden="true" />}
        </button>
      ))}
    </div>
  );

  if (expanded) {
    return (
      <div className="theme-picker theme-picker--expanded">
        <div className="theme-picker__label">Color theme</div>
        {options}
      </div>
    );
  }

  return (
    <div className="theme-picker" ref={rootRef}>
      <button
        type="button"
        className="theme-picker__trigger"
        aria-label={`Color theme: ${activeTheme.label}`}
        aria-haspopup="true"
        aria-expanded={open}
        title="Change color theme"
        onClick={() => setOpen((current) => !current)}
      >
        <Palette size={19} aria-hidden="true" />
        <span>Theme</span>
      </button>
      {open && <div className="theme-picker__menu">{options}</div>}
    </div>
  );
}
