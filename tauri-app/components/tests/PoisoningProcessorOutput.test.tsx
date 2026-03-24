import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PoisoningProcessorOutput from '../PoisoningPage/PoisoningProcessorOutput';

type ProcessingStatus = 'idle' | 'running' | 'done' | 'error';

vi.mock('@tauri-apps/plugin-dialog', () => ({
  open: vi.fn(),
}));

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(),
}));

import { open } from '@tauri-apps/plugin-dialog';
import { invoke } from '@tauri-apps/api/core';

function makeProps(
  overrides: Partial<{
    videoUrl: string;
    intensity: number;
    quality: number;
    poisonedVideoUrl: string;
    setPoisonedVideoUrl: ReturnType<typeof vi.fn>;
    status: ProcessingStatus;
    setStatus: ReturnType<typeof vi.fn>;
    progressMessage: string;
    setProgressMessage: ReturnType<typeof vi.fn>;
    progressPercent: number;
    setProgressPercent: ReturnType<typeof vi.fn>;
    attackResult: any;
    setAttackResult: ReturnType<typeof vi.fn>;
    error: string;
    setError: ReturnType<typeof vi.fn>;
    hasStats: boolean;
    showStats: boolean;
    onToggleStats: ReturnType<typeof vi.fn>;
  }> = {}
) {
  return {
    videoUrl: '',
    intensity: 0.5,
    quality: 80,
    poisonedVideoUrl: '',
    setPoisonedVideoUrl: vi.fn(),
    status: 'idle' as ProcessingStatus,
    setStatus: vi.fn(),
    progressMessage: '',
    setProgressMessage: vi.fn(),
    progressPercent: 0,
    setProgressPercent: vi.fn(),
    attackResult: null,
    setAttackResult: vi.fn(),
    error: '',
    setError: vi.fn(),
    hasStats: false,
    showStats: false,
    onToggleStats: vi.fn(),
    ...overrides,
  };
}

describe('PoisoningProcessorOutput', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows error if Start Process is clicked without input video', () => {
    const props = makeProps();

    render(<PoisoningProcessorOutput {...props} />);

    fireEvent.click(screen.getByRole('button', { name: /start process/i }));

    expect(props.setError).toHaveBeenCalledWith('Please select a video first');
  });

  it('shows error if output folder is missing', () => {
    const props = makeProps({ videoUrl: '/videos/demo.mp4' });

    render(<PoisoningProcessorOutput {...props} />);

    fireEvent.click(screen.getByRole('button', { name: /start process/i }));

    expect(props.setError).toHaveBeenCalledWith('Please select an output folder first');
  });

  it('opens output folder dialog and shows selected folder', async () => {
    vi.mocked(open).mockResolvedValue('/output');

    const props = makeProps({ videoUrl: '/videos/demo.mp4' });

    render(<PoisoningProcessorOutput {...props} />);

    fireEvent.click(screen.getByRole('button', { name: /output destination/i }));

    expect(await screen.findByText('/output')).toBeInTheDocument();
  });

  it('shows dialog error if output folder dialog fails', async () => {
    vi.mocked(open).mockRejectedValue(new Error('folder dialog failed'));

    const props = makeProps({ videoUrl: '/videos/demo.mp4' });

    render(<PoisoningProcessorOutput {...props} />);

    fireEvent.click(screen.getByRole('button', { name: /output destination/i }));

    await waitFor(() => {
      expect(props.setError).toHaveBeenCalledWith('Failed to open folder dialog');
    });
  });

  it('runs attack successfully and updates progress and result state', async () => {
    vi.mocked(open).mockResolvedValue('/output');
    vi.mocked(invoke).mockResolvedValue(
      JSON.stringify({
        adv_path: 'C:\\output\\demo_adv.mp4',
        verified_fooled: true,
        total_time: 12.34,
        attempts: 3,
      })
    );

    const props = makeProps({ videoUrl: '/videos/demo.mp4' });

    render(<PoisoningProcessorOutput {...props} />);

    fireEvent.click(screen.getByRole('button', { name: /output destination/i }));
    await screen.findByText('/output');

    fireEvent.click(screen.getByRole('button', { name: /start process/i }));

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith('run_attack', {
        videoPath: '/videos/demo.mp4',
        outputDir: '/output',
        intensity: 0.5,
        quality: 80,
      });
    });

    expect(props.setStatus).toHaveBeenCalledWith('running');
    expect(props.setProgressMessage).toHaveBeenCalledWith('Starting...');
    expect(props.setProgressPercent).toHaveBeenCalledWith(0);
    expect(props.setAttackResult).toHaveBeenCalled();
    expect(props.setPoisonedVideoUrl).toHaveBeenCalledWith('C:/output/demo_adv.mp4');
    expect(props.setStatus).toHaveBeenCalledWith('done');
    expect(props.setProgressPercent).toHaveBeenCalledWith(100);
  });

  it('sets error state when invoke fails', async () => {
    vi.mocked(open).mockResolvedValue('/output');
    vi.mocked(invoke).mockRejectedValue(new Error('attack failed'));

    const props = makeProps({ videoUrl: '/videos/demo.mp4' });

    render(<PoisoningProcessorOutput {...props} />);

    fireEvent.click(screen.getByRole('button', { name: /output destination/i }));
    await screen.findByText('/output');

    fireEvent.click(screen.getByRole('button', { name: /start process/i }));

    await waitFor(() => {
      expect(props.setStatus).toHaveBeenCalledWith('error');
      expect(props.setError).toHaveBeenCalledWith('attack failed');
      expect(props.setProgressMessage).toHaveBeenCalledWith('');
    });
  });

  it('renders Show Predictions button when hasStats is true', () => {
    const props = makeProps({ hasStats: true });

    render(<PoisoningProcessorOutput {...props} />);

    expect(screen.getByRole('button', { name: /show predictions/i })).toBeInTheDocument();
  });

  it('calls onToggleStats when prediction button is clicked', () => {
    const props = makeProps({ hasStats: true });

    render(<PoisoningProcessorOutput {...props} />);

    fireEvent.click(screen.getByRole('button', { name: /show predictions/i }));

    expect(props.onToggleStats).toHaveBeenCalled();
  });
});