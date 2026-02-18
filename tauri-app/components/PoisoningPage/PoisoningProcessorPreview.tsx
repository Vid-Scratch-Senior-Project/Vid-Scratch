import { convertFileSrc } from "@tauri-apps/api/core";
import MediaBlock from "../MediaBlock";

export default function PoisoningProcessorPreview({videoUrl, poisonedVideoUrl} : {videoUrl: string, poisonedVideoUrl: string}) {


    const normalizePath = (path) => {
        if (!path) return path;
        return path.replace(/\\/g, '/');
    };
    

    return (
        <div
        style={{
            width: '100%',
            height: '100%',
            backgroundColor: 'var(--box-secondary-color)',
            gap: '1rem',
            display: 'flex',
            flexDirection: 'column',
            padding: '1.3rem',
        }}>
            Original
            <div
            style={{
                height: 320
            }}>
                <MediaBlock url={convertFileSrc(normalizePath(videoUrl))} objectFit="contain"/>
            </div>
            
            Poisoned
            <div
            style={{
                height: 320
            }}>
                <MediaBlock url={convertFileSrc(normalizePath(poisonedVideoUrl))} objectFit="contain" />
            </div>
        </div>
    )
}