import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import PoisoningProcessorPreview from '../PoisoningPage/PoisoningProcessorPreview';

vi.mock('@tauri-apps/api/core', () => ({
  convertFileSrc: vi.fn((p: string) => `asset://${p}`),
}));

vi.mock('../MediaBlock', () => ({
  default: ({ url }: { url: string }) => <div data-testid="media-block">{url}</div>,
}));

describe('PoisoningProcessorPreview', () => {
  it('shows No video selected when original video is missing', () => {
    render(
      <PoisoningProcessorPreview
        videoUrl=""
        poisonedVideoUrl=""
        status="idle"
      />
    );

    expect(screen.getByText(/No video selected/i)).toBeInTheDocument();
  });

  it('shows No poisoned video yet when no poisoned output and idle', () => {
    render(
      <PoisoningProcessorPreview
        videoUrl="/videos/a.mp4"
        poisonedVideoUrl=""
        status="idle"
      />
    );

    expect(screen.getByText(/No poisoned video yet/i)).toBeInTheDocument();
  });

  it('shows Processing when status is running and no poisoned output', () => {
    render(
      <PoisoningProcessorPreview
        videoUrl="/videos/a.mp4"
        poisonedVideoUrl=""
        status="running"
      />
    );

    expect(screen.getByTestId('loading-skeleton')).toBeInTheDocument();
  });

  it('shows Processing failed when status is error and no poisoned output', () => {
    render(
      <PoisoningProcessorPreview
        videoUrl="/videos/a.mp4"
        poisonedVideoUrl=""
        status="error"
      />
    );

    expect(screen.getByText(/Processing failed/i)).toBeInTheDocument();
  });

  it('renders original and poisoned media blocks when paths exist', () => {
    render(
      <PoisoningProcessorPreview
        videoUrl="/videos/original.mp4"
        poisonedVideoUrl="/videos/poisoned.mp4"
        status="done"
      />
    );

    expect(screen.getAllByTestId('media-block')).toHaveLength(2);
  });

  it('normalizes backslashes and quotes before convertFileSrc', () => {
    render(
      <PoisoningProcessorPreview
        videoUrl={`"C:\\videos\\original.mp4"`}
        poisonedVideoUrl={`'C:\\videos\\poisoned.mp4'`}
        status="done"
      />
    );

    const blocks = screen.getAllByTestId('media-block');
    expect(blocks[0]).toHaveTextContent('asset://C:/videos/original.mp4');
    expect(blocks[1]).toHaveTextContent('asset://C:/videos/poisoned.mp4');
  });
});