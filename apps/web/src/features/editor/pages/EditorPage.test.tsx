import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ConvexProvider } from 'convex/react';
import { EditorPage } from './EditorPage';

// Mock Convex client
const mockConvexClient = {
  query: () => Promise.resolve(null),
  mutation: () => Promise.resolve(null),
  action: () => Promise.resolve(null),
} as any;

describe('EditorPage', () => {
  it('should render without crashing on initial load', () => {
    expect(() => {
      render(
        <ConvexProvider client={mockConvexClient}>
          <BrowserRouter>
            <EditorPage />
          </BrowserRouter>
        </ConvexProvider>
      );
    }).not.toThrow();
  });

  it('should not have reference errors during initialization', () => {
    // This test ensures variables are declared in the correct order
    // and don't reference variables that haven't been initialized yet
    const consoleSpy = vi.spyOn(console, 'error');
    
    render(
      <ConvexProvider client={mockConvexClient}>
        <BrowserRouter>
          <EditorPage />
        </BrowserRouter>
      </ConvexProvider>
    );

    // Should not have any ReferenceError about 'markdownPreview'
    const referenceErrors = consoleSpy.mock.calls.filter(
      (call: unknown[]) => call[0]?.toString().includes('Cannot access')
    );
    
    expect(referenceErrors).toHaveLength(0);
    
    consoleSpy.mockRestore();
  });
});
