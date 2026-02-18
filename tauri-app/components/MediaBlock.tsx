import React, { useEffect, useRef } from 'react';
import detectMediaType from '../utils/detectMediaType';

type MediaBlockProps = {
    url: string;
    alt?: string;
    className?: string;
    objectFit?: React.CSSProperties['objectFit'];
    videoOptions?: {
        controls?: boolean;
        autoPlay?: boolean;
        loop?: boolean;
        muted?: boolean;
    };
};
export default function MediaBlock({
    url,
    alt = '',
    className = '',
    objectFit = 'cover',
    videoOptions = {
        controls: true,
        autoPlay: false,
        loop: false,
        muted: true
    } }: MediaBlockProps) {
    // Validate URL first
    if (!url) {
        return (
            <div className={`media-block ${className}`}
                style={{
                    position: 'relative',
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: '#f0f0f0'
                }}>
                <p>Missing media URL</p>
            </div>
        );
    }

    // Check media type with more robust validation
    const mediaType = detectMediaType(url)

    const isYouTube = (mediaType === 'youtube');
    const isTikTok = (mediaType === 'tiktok');
    const isVideo = (mediaType === 'video');
    const isImage = (mediaType === 'image');

    // YouTube embed
    if (isYouTube) {
        const videoId = getYouTubeId(url);
        if (!videoId) return renderError('Invalid YouTube URL');

        const youTubeEmbedOptions = {
            autoplay: videoOptions.autoPlay ? 1 : 0,
            loop: videoOptions.loop ? 1 : 0,
            mute: videoOptions.muted ? 1 : 0,
            controls: videoOptions.controls ? 1 : 0,
            modestbranding: 1,
            rel: 0
        };
        const youTubeParams = new URLSearchParams(youTubeEmbedOptions as any).toString();

        return (
            <div style={{ position: 'relative', width: '100%', height: '100%' }}>
                <iframe
                    src={`https://www.youtube.com/embed/${videoId}?${youTubeParams}`}
                    title={alt}
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                    style={{ width: '100%', height: '100%', border: 'none' }}
                />
            </div>
        );
    }

    // TikTok embed
    if (isTikTok) {
        return (
            <div style={{
                position: 'relative',
                width: '100%',
                height: '100%',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center'
            }}>
                <p>TikTok embedding would go here</p>
            </div>
        );
    }


    // Video file
    if (isVideo) {

        const videoRef = useRef(null);
    
    useEffect(() => {
        if (videoRef.current && url) {
            if (videoOptions.autoPlay) {
                videoRef.current.play().catch(e => console.log("Autoplay prevented:", e));
            }
        }
    }, [url, videoOptions.autoPlay]);

    return (
        <video
            ref={videoRef}
            src={url}  // Direct src attribute, no source tag needed
            controls={videoOptions.controls}
            playsInline
            muted={videoOptions.muted}
            autoPlay={videoOptions.autoPlay}
            loop={videoOptions.loop}
            style={{
                width: '100%',
                height: '100%',
                objectFit: objectFit || 'contain',
                backgroundColor: 'black'
            }}
            onError={(e) => {
                console.error("Video error:", e.target.error);
                console.error("URL that failed:", url);
            }}
        />
    );
    }

    // Image file
    if (isImage) {
        return (
            <div style={{
                position: 'relative',
                width: '100%',
                height: '100%',
                overflow: 'hidden'
            }}>
                <img
                    src={url}
                    alt={alt}
                    style={{
                        width: '100%',
                        height: '100%',
                        objectFit: objectFit,
                        objectPosition: 'center',
                        display: 'block'
                    }}
                    loading="lazy"
                />
            </div>
        );
    }

    // Unsupported type
    return renderError('Unsupported media type');

    // Helper functions
    function getYouTubeId(url: string) {
        const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
        const match = url.match(regExp);
        return (match && match[2].length === 11) ? match[2] : null;
    }

    function renderError(message: string) {
        return (
            <div style={{
                position: 'relative',
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: '#f0f0f0',
                color: '#ff0000'
            }}>
                <p>{message}: {url}</p>
            </div>
        );
    }
}