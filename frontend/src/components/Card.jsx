import React from 'react';

/**
 * Simple reusable Card component adhering to the design system.
 * Applies the global `.card` class for styling and accepts optional extra className.
 */
export default function Card({ children, className = '' }) {
  return (
    <div className={`card ${className}`.trim()}>
      {children}
    </div>
  );
}
