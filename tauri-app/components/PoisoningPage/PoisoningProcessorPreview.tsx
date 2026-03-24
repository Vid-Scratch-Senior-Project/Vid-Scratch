// import { convertFileSrc } from "@tauri-apps/api/core";
// import MediaBlock from "../MediaBlock";

// export default function PoisoningProcessorPreview({videoUrl, poisonedVideoUrl} : {videoUrl: string, poisonedVideoUrl: string}) {


//     const normalizePath = (path) => {
//         if (!path) return path;
//         return path.replace(/\\/g, '/');
//     };
    

//     return (
//         <div
//         style={{
//             width: '100%',
//             height: '100%',
//             backgroundColor: 'var(--box-secondary-color)',
//             gap: '1rem',
//             display: 'flex',
//             flexDirection: 'column',
//             padding: '1.3rem',
//         }}>
//             Original
//             <div
//             style={{
//                 height: 320
//             }}>
//                 <MediaBlock url={convertFileSrc(normalizePath(videoUrl))} objectFit="contain"/>
//             </div>
            
//             Poisoned
//             <div
//             style={{
//                 height: 320
//             }}>
//                 <MediaBlock url={convertFileSrc(normalizePath(poisonedVideoUrl))} objectFit="contain" />
//             </div>
//         </div>
//     )
// }

import { convertFileSrc } from "@tauri-apps/api/core";
import MediaBlock from "../MediaBlock";
import type { ProcessingStatus } from "./PoisoningProcessor";

interface Props {
    videoUrl: string;
    poisonedVideoUrl: string;
    status: ProcessingStatus;
}

export default function PoisoningProcessorPreview({
    videoUrl,
    poisonedVideoUrl,
    status,
}: Props) {

    const normalizePath = (path: string) => {
        if (!path) return path;
        return path.replace(/\\/g, '/').replace(/['"]/g, '');
    };

    return (
        <div style={{
            flex: 1,
            height: '100%',
            backgroundColor: 'var(--box-secondary-color)',
            display: 'flex',
            flexDirection: 'column',
            padding: '1rem',
            gap: '0.5rem',
        }}>
            {/* Original */}
            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Original</span>
            <div style={{ flex: 1, minHeight: 0 }}>
                {videoUrl ? (
                    <MediaBlock url={convertFileSrc(normalizePath(videoUrl))} objectFit="contain" />
                ) : (
                    <div style={{
                        height: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--septenary-text-color)',
                        fontSize: '0.85rem',
                        backgroundColor: '#000',
                        borderRadius: '4px',
                    }}>
                        No video selected
                    </div>
                )}
            </div>

            {/* Poisoned */}
            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Poisoned</span>
            <div style={{ flex: 1, minHeight: 0 }}>
                {poisonedVideoUrl ? (
                    <MediaBlock url={convertFileSrc(normalizePath(poisonedVideoUrl))} objectFit="contain" />
                ) : (
                    <div style={{
                        height: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--septenary-text-color)',
                        fontSize: '0.85rem',
                        backgroundColor: '#000',
                        borderRadius: '4px',
                    }}>
                        {status === 'running' ? 'Processing...' :
                         status === 'error' ? 'Processing failed' :
                         'No poisoned video yet'}
                    </div>
                )}
            </div>
        </div>
    );
}