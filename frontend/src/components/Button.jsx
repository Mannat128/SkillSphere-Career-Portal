import React from 'react';

/**
 * Reusable button component that follows the approved design system.
 * Uses the global `.btn` class for spacing, borders, and transitions.
 * The primary colour is Neon Lime (`var(--color-neon)`) with dark/black text.
 */
export default function Button({ children, onClick, type = 'button', disabled = false }) {
  const baseStyle = {
    background: 'var(--color-neon)',
    color: 'var(--color-midnight)',
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className="btn"
      style={baseStyle}
    >
      {children}
    </button>
  );
}
