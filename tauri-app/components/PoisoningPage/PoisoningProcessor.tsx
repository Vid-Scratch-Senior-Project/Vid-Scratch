// 'use client'

// import { useState } from "react";
// import { listen } from "@tauri-apps/api/event";
// import { useEffect } from "react";
// import PoisoningProcessorInput from "./PoisoningProcessorInput";
// import PoisoningProcessorOutput from "./PoisoningProcessorOutput";
// import PoisoningProcessorPreview from "./PoisoningProcessorPreview";
// import PoisoningProcessorSettings from "./PoisoningProcessorSettings";


// export interface AttackResult {
//     verified_fooled: boolean;
//     adv_path: string;
//     orig_pred: number;
//     orig_pred_name: string;
//     verified_pred: number;
//     verified_pred_name: string;
//     orig_confidence: number;
//     adv_confidence: number;
//     ssim: number;
//     psnr: number;
//     noise_clamp: number;
//     ssim_budget: number;
//     attempts: number;
//     total_time: number;
//     total_frames: number;
//     frames_poisoned: number;
//     key_frames: number[];
// }

// export type ProcessingStatus = 'idle' | 'running' | 'done' | 'error';

// export default function PoisoningProcessor() {

//     const [intensity, setIntensity] = useState(25);
//     const [quality, setQuality] = useState(50);
//     const [videoUrl, setVideoUrl] = useState("");
//     const [poisonedVideoUrl, setPoisonedVideoUrl] = useState("");

//     const [status, setStatus] = useState<ProcessingStatus>('idle');
//     const [progressMessage, setProgressMessage] = useState("");
//     const [attackResult, setAttackResult] = useState<AttackResult | null>(null);
//     const [error, setError] = useState("");

//     // Listen to progress events from Tauri backend
//     useEffect(() => {
//         const unlisten = listen<{ stage: string; message: string }>(
//             "attack-progress",
//             (event) => {
//                 setProgressMessage(event.payload.message);
//                 if (event.payload.stage === "error") {
//                     setStatus("error");
//                     setError(event.payload.message);
//                 }
//             }
//         );

//         return () => {
//             unlisten.then((fn) => fn());
//         };
//     }, []);

//     return (
//         <div
//             style={{
//                 fontFamily: 'var(--font-poppins)'
//             }}>
//             <div
//                 style={{
//                     display: 'flex',
//                     gap: '0.3rem',
//                     justifyContent: 'space-between',
//                 }}>
//                 <div
//                     style={{
//                         display: 'flex',
//                         flexDirection: 'column',
//                         width: '100%',
//                         height: '100%',
//                         gap: '0.3rem',
//                     }}>
//                     <PoisoningProcessorInput filepath={videoUrl} setFilepath={setVideoUrl} />
//                     <PoisoningProcessorSettings
//                         intensity={intensity}
//                         quality={quality}
//                         setIntensity={setIntensity}
//                         setQuality={setQuality}
//                     />
//                     <PoisoningProcessorOutput
//                         videoUrl={videoUrl}
//                         intensity={intensity}
//                         quality={quality}
//                         poisonedVideoUrl={poisonedVideoUrl}
//                         setPoisonedVideoUrl={setPoisonedVideoUrl}
//                         status={status}
//                         setStatus={setStatus}
//                         progressMessage={progressMessage}
//                         setProgressMessage={setProgressMessage}
//                         attackResult={attackResult}
//                         setAttackResult={setAttackResult}
//                         error={error}
//                         setError={setError}
//                     />
//                 </div>
//                 <PoisoningProcessorPreview videoUrl={videoUrl} poisonedVideoUrl={poisonedVideoUrl} />
//             </div>
//         </div>
//     )
// }

'use client'

import { useState, useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { LogicalSize } from "@tauri-apps/api/dpi";
import PoisoningProcessorInput from "./PoisoningProcessorInput";
import PoisoningProcessorOutput from "./PoisoningProcessorOutput";
import PoisoningProcessorPreview from "./PoisoningProcessorPreview";
import PoisoningProcessorSettings from "./PoisoningProcessorSettings";


export interface PredictionEntry {
    classId: number;
    className: string;
    confidence: number;
}

export interface AttackResult {
    verified_fooled: boolean;
    adv_path: string;
    orig_pred: number;
    orig_pred_name: string;
    verified_pred: number;
    verified_pred_name: string;
    orig_confidence: number;
    adv_confidence: number;
    ssim: number;
    psnr: number;
    noise_clamp: number;
    ssim_budget: number;
    attempts: number;
    total_time: number;
    total_frames: number;
    frames_poisoned: number;
    key_frames: number[];
    orig_top5?: [number, number][];
    adv_top5?: [number, number][];
    orig_top5_names?: string[];
    adv_top5_names?: string[];
}

export type ProcessingStatus = 'idle' | 'running' | 'done' | 'error';

const BASE_WIDTH = 1030;
const EXPANDED_WIDTH = 1545;
const WINDOW_HEIGHT = 800;

export default function PoisoningProcessor() {

    const [intensity, setIntensity] = useState(25);
    const [quality, setQuality] = useState(50);
    const [videoUrl, setVideoUrl] = useState("");
    const [poisonedVideoUrl, setPoisonedVideoUrl] = useState("");

    const [status, setStatus] = useState<ProcessingStatus>('idle');
    const [progressMessage, setProgressMessage] = useState("");
    const [attackResult, setAttackResult] = useState<AttackResult | null>(null);
    const [error, setError] = useState("");

    const [cleanPredictions, setCleanPredictions] = useState<PredictionEntry[]>([]);
    const [poisonedPredictions, setPoisonedPredictions] = useState<PredictionEntry[]>([]);
    const [showStats, setShowStats] = useState(false);

    const toggleStats = async () => {
        const next = !showStats;
        setShowStats(next);
        try {
            const appWindow = getCurrentWindow();
            await appWindow.setResizable(true);
            await appWindow.setSize(new LogicalSize(next ? EXPANDED_WIDTH : BASE_WIDTH, WINDOW_HEIGHT));
            await appWindow.center();
            await appWindow.setResizable(false);
        } catch (e) {
            console.error('Window resize error:', e);
        }
    };

    useEffect(() => {
        const unlisten = listen<{ stage: string; message: string }>(
            "attack-progress",
            (event) => {
                setProgressMessage(event.payload.message);
                if (event.payload.stage === "error") {
                    setStatus("error");
                    setError(event.payload.message);
                }
            }
        );
        return () => { unlisten.then((fn) => fn()); };
    }, []);

    useEffect(() => {
        if (!attackResult) return;

        if (attackResult.orig_top5 && attackResult.orig_top5_names) {
            setCleanPredictions(attackResult.orig_top5.map(
                ([classId, conf], i) => ({
                    classId,
                    className: attackResult.orig_top5_names?.[i] || `class_${classId}`,
                    confidence: conf,
                })
            ));
        } else {
            setCleanPredictions([{
                classId: attackResult.orig_pred,
                className: attackResult.orig_pred_name,
                confidence: attackResult.orig_confidence,
            }]);
        }

        if (attackResult.adv_top5 && attackResult.adv_top5_names) {
            setPoisonedPredictions(attackResult.adv_top5.map(
                ([classId, conf], i) => ({
                    classId,
                    className: attackResult.adv_top5_names?.[i] || `class_${classId}`,
                    confidence: conf,
                })
            ));
        } else {
            setPoisonedPredictions([{
                classId: attackResult.verified_pred,
                className: attackResult.verified_pred_name,
                confidence: attackResult.adv_confidence,
            }]);
        }
    }, [attackResult]);

    useEffect(() => {
        setCleanPredictions([]);
        setPoisonedPredictions([]);
        setPoisonedVideoUrl("");
        setAttackResult(null);
        setStatus('idle');
        setError("");
        setProgressMessage("");
        if (showStats) {
            setShowStats(false);
            const appWindow = getCurrentWindow();
            appWindow.setResizable(true).then(() =>
                appWindow.setSize(new LogicalSize(BASE_WIDTH, WINDOW_HEIGHT)).then(() =>
                    appWindow.center().then(() =>
                        appWindow.setResizable(false)
                    )
                )
            ).catch(() => {});
        }
    }, [videoUrl]);

    const hasStats = cleanPredictions.length > 0 || poisonedPredictions.length > 0;

    return (
        <div style={{
            fontFamily: 'var(--font-poppins)',
            width: '100%',
            height: '100vh',
            overflow: 'hidden',
        }}>
            <div style={{
                display: 'flex',
                height: '100%',
                overflow: 'hidden',
            }}>
                {/* Column 1: Controls — 1/3 of current window */}
                <div style={{
                    flex: 1,
                    minWidth: 0,
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.3rem',
                    overflowY: 'auto',
                }}>
                    <PoisoningProcessorInput filepath={videoUrl} setFilepath={setVideoUrl} />
                    <PoisoningProcessorSettings
                        intensity={intensity}
                        quality={quality}
                        setIntensity={setIntensity}
                        setQuality={setQuality}
                    />
                    <PoisoningProcessorOutput
                        videoUrl={videoUrl}
                        intensity={intensity}
                        quality={quality}
                        poisonedVideoUrl={poisonedVideoUrl}
                        setPoisonedVideoUrl={setPoisonedVideoUrl}
                        status={status}
                        setStatus={setStatus}
                        progressMessage={progressMessage}
                        setProgressMessage={setProgressMessage}
                        attackResult={attackResult}
                        setAttackResult={setAttackResult}
                        error={error}
                        setError={setError}
                        hasStats={hasStats}
                        showStats={showStats}
                        onToggleStats={toggleStats}
                    />
                </div>

                {/* Column 2: Video previews — 1/3 of current window */}
                <div style={{
                    flex: 1,
                    minWidth: 0,
                    height: '100%',
                    overflow: 'hidden',
                }}>
                    <PoisoningProcessorPreview
                        videoUrl={videoUrl}
                        poisonedVideoUrl={poisonedVideoUrl}
                        status={status}
                    />
                </div>

                {/* Column 3: Stats — 1/3, only when expanded */}
                {showStats && hasStats && (
                    <div style={{
                        flex: 1,
                        minWidth: 0,
                        height: '100%',
                        display: 'flex',
                        flexDirection: 'column',
                        backgroundColor: 'var(--box-secondary-color)',
                        overflow: 'hidden',
                        animation: 'slideIn 0.2s ease-out',
                    }}>
                        {/* Top: Clean predictions */}
                        <div style={{
                            flex: 1,
                            padding: '1rem',
                            overflowY: 'auto',
                            borderBottom: '1px solid rgba(255,255,255,0.05)',
                        }}>
                            <PredictionPanel
                                title="Clean - Top-5 Predictions"
                                titleColor="#60a5fa"
                                predictions={cleanPredictions}
                                barColor="#3b82f6"
                            />
                        </div>

                        {/* Bottom: Poisoned predictions */}
                        <div style={{
                            flex: 1,
                            padding: '1rem',
                            overflowY: 'auto',
                        }}>
                            {poisonedPredictions.length > 0 ? (
                                <PredictionPanel
                                    title="Poisoned - Top-5 Predictions"
                                    titleColor="#f87171"
                                    predictions={poisonedPredictions}
                                    barColor="#ef4444"
                                />
                            ) : (
                                <div style={{
                                    height: '100%',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    color: 'var(--septenary-text-color)',
                                    fontSize: '0.8rem',
                                }}>
                                    No poisoned predictions yet
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>

            <style>{`
                @keyframes slideIn {
                    from { opacity: 0; transform: translateX(20px); }
                    to { opacity: 1; transform: translateX(0); }
                }
            `}</style>
        </div>
    );
}


// ── Prediction Panel ────────────────────────────────────────────────────────

export function PredictionPanel({
    title,
    titleColor,
    predictions,
    barColor,
}: {
    title: string;
    titleColor: string;
    predictions: PredictionEntry[];
    barColor: string;
}) {
    if (predictions.length === 0) return null;

    const topPred = predictions[0];
    const maxConf = Math.max(...predictions.map(p => p.confidence), 0.01);

    return (
        <div style={{
            backgroundColor: 'rgba(0,0,0,0.3)',
            borderRadius: '8px',
            padding: '12px',
        }}>
            <div style={{
                fontSize: '0.62rem',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                color: titleColor,
                marginBottom: '4px',
                fontWeight: 600,
            }}>
                {title}
            </div>
            <div style={{
                fontSize: '1rem',
                fontWeight: 700,
                color: 'var(--primary-text-color)',
                marginBottom: '2px',
            }}>
                {topPred.className}
            </div>
            <div style={{
                fontSize: '0.68rem',
                color: 'var(--septenary-text-color)',
                marginBottom: '10px',
            }}>
                Class #{topPred.classId} · Confidence: {(topPred.confidence * 100).toFixed(1)}%
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                {predictions.map((pred, i) => (
                    <div key={i} style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                    }}>
                        <span style={{
                            color: 'var(--septenary-text-color)',
                            minWidth: '16px',
                            textAlign: 'right',
                            fontSize: '0.65rem',
                        }}>
                            #{i + 1}
                        </span>
                        <div style={{
                            flex: 1,
                            position: 'relative',
                            height: '22px',
                            backgroundColor: 'rgba(255,255,255,0.05)',
                            borderRadius: '3px',
                            overflow: 'hidden',
                        }}>
                            <div style={{
                                position: 'absolute',
                                left: 0, top: 0, bottom: 0,
                                width: `${Math.max((pred.confidence / maxConf) * 100, 2)}%`,
                                backgroundColor: i === 0 ? barColor : 'rgba(255,255,255,0.1)',
                                borderRadius: '3px',
                                transition: 'width 0.4s ease',
                            }} />
                            <span style={{
                                position: 'relative',
                                zIndex: 1,
                                lineHeight: '22px',
                                paddingLeft: '6px',
                                color: i === 0 ? '#fff' : 'var(--septenary-text-color)',
                                fontWeight: i === 0 ? 600 : 400,
                                fontSize: '0.68rem',
                                whiteSpace: 'nowrap',
                            }}>
                                {pred.className}
                            </span>
                        </div>
                        <span style={{
                            color: 'var(--septenary-text-color)',
                            minWidth: '42px',
                            textAlign: 'right',
                            fontSize: '0.68rem',
                        }}>
                            {(pred.confidence * 100).toFixed(1)}%
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}