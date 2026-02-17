
import React from "react";

export default function PoisoningProcessorSettings({intensity, quality, setIntensity, setQuality} : {intensity: number, quality: number, setIntensity: (value: number) => void, setQuality: (value: number) => void}) {

    return (
        <React.Fragment>
            <div className="text-lg font-semibold"
                style={{
                    backgroundColor: 'var(--box-primary-color)',
                    width: '100%',
                    padding: 10
                }}>
                2. Define Settings
            </div>
            <div className="flex flex-col gap-2 p-4"
                style={{
                    backgroundColor: 'var(--box-secondary-color)',
                    width: '100%',
                }}>
                <div
                    style={{
                        fontSize: '1.4rem'
                    }}>
                    Intensity
                </div>
                <div
                    style={{
                        fontSize: '0.8rem',
                        color: 'var(--septenary-text-color)'
                    }}>
                    Magnitude of changes that will add to your video. Higher values can lead to more visible change but stronger protection.
                </div>
                <div className="w-full p-2">
                    <input type="range" min={0} max="100" value={intensity}
                        onChange={(e) => setIntensity(parseInt(e.target.value))}
                        step="25" className="w-full range range-primary [--range-bg:#5c98e22f]" />
                    <div className="flex justify-between px-2.5 mt-2 text-xs">
                        <span className="text-center w-[20px] -ml-2">Very Low</span>
                        <span className="text-center w-[20px]">Low</span>
                        <span className="text-center w-[20px]">Mid</span>
                        <span className="text-center w-[20px]">High</span>
                        <span className="text-center w-[20px] -mr-2">Very High</span>
                    </div>
                </div>
            </div>
            <div className="flex flex-col gap-2 p-4"
                style={{
                    backgroundColor: 'var(--box-secondary-color)',
                    width: '100%',
                }}>
                <div
                    style={{
                        fontSize: '1.4rem'
                    }}>
                    Render Quality
                </div>
                <div
                    style={{
                        fontSize: '0.8rem',
                        color: 'var(--septenary-text-color)'
                    }}>
                    Duration spent protractoring the video. Higher can lead to better Protection but longer rendering time.
                </div>
                <div className="w-full p-2">
                    <input type="range" min={0} max="100" value={quality}
                        onChange={(e) => setQuality(parseInt(e.target.value))}
                        className="w-full range range-primary [--range-bg:#5c98e22f]" step="25" />
                    <div className="flex justify-between px-2.5 mt-2 text-xs">
                        <span className="text-center w-[25px] -ml-2">Low</span>
                        <span className="text-center w-[50px]">Medium</span>
                        <span className="text-center w-[25px] -mr-2">High</span>
                    </div>
                </div>
            </div>
        </React.Fragment>
    )
}