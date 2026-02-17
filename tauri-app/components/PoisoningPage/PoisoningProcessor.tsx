'use client'

import { useState } from "react";
import PoisoningProcessorInput from "./PoisoningProcessorInput";
import PoisoningProcessorOutput from "./PoisoningProcessorOutput";
import PoisoningProcessorPreview from "./PoisoningProcessorPreview";
import PoisoningProcessorSettings from "./PoisoningProcessorSettings";


export default function PoisoningProcessor() {

    const [intensity, setIntensity] = useState(25);
    const [quality, setQuality] = useState(25);
    const [videoUrl, setVideoUrl] = useState("");
    const [poisonedVideoUrl, setPoisonedVideoUrl] = useState("/tue_8sec_stronger.mp4");

    return (
        <div
            style={{
                fontFamily: 'var(--font-poppins)'
            }}>
            <div
                style={{
                    display: 'flex',
                    gap: '0.3rem',
                    justifyContent: 'space-between',
                }}>
                <div
                    style={{
                        display: 'flex',
                        flexDirection: 'column',
                        width: '100%',
                        height: '100%',
                        gap: '0.3rem',
                    }}>
                    <PoisoningProcessorInput filename={videoUrl} setFilename={setVideoUrl} />
                    <PoisoningProcessorSettings intensity={intensity} quality={quality} setIntensity={setIntensity} setQuality={setQuality} />
                    <PoisoningProcessorOutput videoUrl={videoUrl} intensity={intensity} quality={quality} poisonedVideoUrl={poisonedVideoUrl} setPoisonedVideoUrl={setPoisonedVideoUrl} />
                </div>
                <PoisoningProcessorPreview videoUrl={videoUrl} poisonedVideoUrl={poisonedVideoUrl} />
            </div>

        </div>
    )
}