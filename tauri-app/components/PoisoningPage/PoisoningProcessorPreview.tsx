import MediaBlock from "../MediaBlock";

export default function PoisoningProcessorPreview({videoUrl, poisonedVideoUrl} : {videoUrl: string, poisonedVideoUrl: string}) {

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
                height: 300
            }}>
                <MediaBlock url={videoUrl} objectFit="contain"/>
            </div>
            
            Poisoned
            <div
            style={{
                height: 300
            }}>
                <MediaBlock url={poisonedVideoUrl} objectFit="contain" />
            </div>
        </div>
    )
}