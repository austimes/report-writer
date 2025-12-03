import { describe, it, expect } from 'vitest';
import { getLineRange, getLineCount } from './lineNumbers';

describe('lineNumbers', () => {
  describe('getLineCount', () => {
    it('should count lines correctly', () => {
      expect(getLineCount('line1')).toBe(1);
      expect(getLineCount('line1\nline2')).toBe(2);
      expect(getLineCount('line1\nline2\nline3')).toBe(3);
      expect(getLineCount('')).toBe(1);
    });
  });

  describe('getLineRange', () => {
    it('should calculate line range for first heading', () => {
      const markdown = '# Introduction\n\n# Ampol 2025';
      // "# Introduction\n" is characters 0-15 (includes the newline)
      // Adding the blank line: 0-16
      const result = getLineRange(markdown, 0, 16);
      
      expect(result.startLine).toBe(1); // Should include the heading line
      expect(result.endLine).toBe(2); // Should include blank line after heading
      expect(result.totalLines).toBe(3);
    });

    it('should calculate line range for section starting at offset 0', () => {
      const markdown = '# Introduction\n\n';
      const result = getLineRange(markdown, 0, 16);
      
      expect(result.startLine).toBe(1);
      expect(result.endLine).toBe(2);
    });

    it('should calculate line range for middle section', () => {
      const markdown = '# Introduction\n\n# Ampol 2025\n\nContent here';
      // "# Ampol 2025\n" starts at character 16
      const result = getLineRange(markdown, 16, 45);
      
      expect(result.startLine).toBe(3); // "# Ampol 2025" is on line 3
      expect(result.endLine).toBe(5); // Should include content
    });

    it('should handle single-line sections', () => {
      const markdown = '# Title';
      const result = getLineRange(markdown, 0, 7);
      
      expect(result.startLine).toBe(1);
      expect(result.endLine).toBe(1);
    });

    it('should handle sections with multiple lines', () => {
      const markdown = '# Heading\nLine 1\nLine 2\nLine 3';
      const result = getLineRange(markdown, 0, markdown.length);
      
      expect(result.startLine).toBe(1);
      expect(result.endLine).toBe(4);
    });
  });
});
