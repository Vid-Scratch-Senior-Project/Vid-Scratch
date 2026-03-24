import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PoisoningProcessorInput from '../PoisoningPage/PoisoningProcessorInput';

vi.mock('@tauri-apps/plugin-dialog', () => ({
  open: vi.fn(),
}));

vi.mock('../../utils/detectMediaType', () => ({
  default: vi.fn(),
}));

import { open } from '@tauri-apps/plugin-dialog';
import detectMediaType from '../../utils/detectMediaType';

describe('PoisoningProcessorInput', () => {
  const setFilepath = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders selected filepath when filepath prop exists', () => {
    render(
      <PoisoningProcessorInput
        filepath="/videos/demo.mp4"
        setFilepath={setFilepath}
      />
    );

    expect(screen.getByText(/Selected video:/i)).toHaveTextContent('/videos/demo.mp4');
  });

  it('opens file dialog when Select Video is clicked', async () => {
    vi.mocked(open).mockResolvedValue('/videos/demo.mp4');
    vi.mocked(detectMediaType).mockReturnValue('video');

    render(<PoisoningProcessorInput filepath="" setFilepath={setFilepath} />);

    fireEvent.click(screen.getByRole('button', { name: /select video/i }));

    await waitFor(() => {
      expect(open).toHaveBeenCalled();
    });
  });

  it('sets filepath when selected file is a video', async () => {
    vi.mocked(open).mockResolvedValue('/videos/demo.mp4');
    vi.mocked(detectMediaType).mockReturnValue('video');

    render(<PoisoningProcessorInput filepath="" setFilepath={setFilepath} />);

    fireEvent.click(screen.getByRole('button', { name: /select video/i }));

    await waitFor(() => {
      expect(setFilepath).toHaveBeenCalledWith('/videos/demo.mp4');
    });
  });

  it('shows error when selected file is not a supported video', async () => {
    vi.mocked(open).mockResolvedValue('/files/demo.txt');
    vi.mocked(detectMediaType).mockReturnValue('unknown');

    render(<PoisoningProcessorInput filepath="" setFilepath={setFilepath} />);

    fireEvent.click(screen.getByRole('button', { name: /select video/i }));

    expect(await screen.findByText(/Only video files are supported/i)).toBeInTheDocument();
    expect(setFilepath).not.toHaveBeenCalled();
  });

  it('shows error when file dialog fails', async () => {
    vi.mocked(open).mockRejectedValue(new Error('dialog failed'));

    render(<PoisoningProcessorInput filepath="" setFilepath={setFilepath} />);

    fireEvent.click(screen.getByRole('button', { name: /select video/i }));

    expect(await screen.findByText(/Failed to open file dialog/i)).toBeInTheDocument();
  });

  it('shows Opening while dialog is in progress', async () => {
    let resolveOpen: (value: string) => void = () => {};

    vi.mocked(open).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveOpen = resolve as (value: string) => void;
        }) as any
    );
    vi.mocked(detectMediaType).mockReturnValue('video');

    render(<PoisoningProcessorInput filepath="" setFilepath={setFilepath} />);

    fireEvent.click(screen.getByRole('button', { name: /select video/i }));

    expect(screen.getByRole('button')).toHaveTextContent(/opening/i);

    resolveOpen('/videos/demo.mp4');

    await waitFor(() => {
      expect(screen.getByRole('button')).toHaveTextContent(/select video/i);
    });
  });
});