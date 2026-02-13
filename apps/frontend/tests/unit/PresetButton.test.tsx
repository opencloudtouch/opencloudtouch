import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import PresetButton, { type Preset } from '../../src/components/PresetButton'

describe('PresetButton Component', () => {
  const mockOnAssign = vi.fn()
  const mockOnClear = vi.fn()
  const mockOnPlay = vi.fn()

  const mockPreset: Preset = {
    station_name: 'BBC Radio 1',
  }

  beforeEach(() => {
    mockOnAssign.mockClear()
    mockOnClear.mockClear()
    mockOnPlay.mockClear()
  })

  describe('Empty Preset', () => {
    it('renders empty state with placeholder text', () => {
      render(
        <PresetButton
          number={1}
          preset={null}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      )

      expect(screen.getByText('1')).toBeInTheDocument()
      expect(screen.getByText('Preset zuweisen')).toBeInTheDocument()
    })

    it('renders empty state when preset is undefined', () => {
      render(
        <PresetButton
          number={2}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      )

      expect(screen.getByText('2')).toBeInTheDocument()
      expect(screen.getByText('Preset zuweisen')).toBeInTheDocument()
    })

    it('calls onAssign when empty preset is clicked', () => {
      render(
        <PresetButton
          number={1}
          preset={null}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      )

      const button = screen.getByText('Preset zuweisen').closest('button')
      fireEvent.click(button!)

      expect(mockOnAssign).toHaveBeenCalledTimes(1)
      expect(mockOnPlay).not.toHaveBeenCalled()
      expect(mockOnClear).not.toHaveBeenCalled()
    })

    it('applies preset-empty CSS class', () => {
      render(
        <PresetButton
          number={1}
          preset={null}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      )

      const button = screen.getByText('Preset zuweisen').closest('button')
      expect(button).toHaveClass('preset-empty')
    })
  })

  describe('Assigned Preset', () => {
    it('renders assigned preset with station name', () => {
      render(
        <PresetButton
          number={3}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      )

      expect(screen.getByText('3')).toBeInTheDocument()
      expect(screen.getByText('BBC Radio 1')).toBeInTheDocument()
    })

    it('calls onPlay when preset play button is clicked', () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      )

      const playButton = screen.getByText('BBC Radio 1').closest('button')
      fireEvent.click(playButton!)

      expect(mockOnPlay).toHaveBeenCalledTimes(1)
      expect(mockOnAssign).not.toHaveBeenCalled()
      expect(mockOnClear).not.toHaveBeenCalled()
    })

    it('calls onClear when clear button is clicked', () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      )

      const clearButton = screen.getByLabelText('Clear preset')
      fireEvent.click(clearButton)

      expect(mockOnClear).toHaveBeenCalledTimes(1)
      expect(mockOnAssign).not.toHaveBeenCalled()
      expect(mockOnPlay).not.toHaveBeenCalled()
    })

    it('renders both play and clear buttons', () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      )

      const playButton = document.querySelector('.preset-play')
      const clearButton = document.querySelector('.preset-clear')

      expect(playButton).toBeInTheDocument()
      expect(clearButton).toBeInTheDocument()
    })

    it('applies correct CSS classes for assigned preset', () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      )

      const playButton = screen.getByText('BBC Radio 1').closest('button')
      const clearButton = screen.getByLabelText('Clear preset')

      expect(playButton).toHaveClass('preset-play')
      expect(clearButton).toHaveClass('preset-clear')
    })
  })

  describe('Preset Number Display', () => {
    it('displays correct preset number for different slots', () => {
      const { rerender } = render(
        <PresetButton
          number={1}
          preset={null}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      )
      expect(screen.getByText('1')).toBeInTheDocument()

      rerender(
        <PresetButton
          number={6}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      )
      expect(screen.getByText('6')).toBeInTheDocument()
    })

    it('renders preset number within preset-number span', () => {
      render(
        <PresetButton
          number={4}
          preset={null}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      )

      const numberSpan = document.querySelector('.preset-number')
      expect(numberSpan).toBeInTheDocument()
      expect(numberSpan).toHaveTextContent('4')
    })
  })

  describe('Container Element', () => {
    it('wraps content in preset-button container', () => {
      render(
        <PresetButton
          number={1}
          preset={null}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      )

      const container = document.querySelector('.preset-button')
      expect(container).toBeInTheDocument()
    })
  })
})
