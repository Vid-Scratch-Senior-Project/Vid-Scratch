'use client'

import { RiFolder5Fill } from "@remixicon/react";
import React from "react";
import { open } from '@tauri-apps/plugin-dialog';
import { invoke } from "@tauri-apps/api/core";
import type { AttackResult, ProcessingStatus } from "./PoisoningProcessor";


interface Props {
    videoUrl: string;
    intensity: number;
    quality: number;
    poisonedVideoUrl: string;
    setPoisonedVideoUrl: (url: string) => void;
    status: ProcessingStatus;
    setStatus: (status: ProcessingStatus) => void;
    progressMessage: string;
    setProgressMessage: (msg: string) => void;
    progressPercent: number;
    setProgressPercent: (pct: number) => void;
    attackResult: AttackResult | null;
    setAttackResult: (result: AttackResult | null) => void;
    error: string;
    setError: (error: string) => void;
    hasStats: boolean;
    showStats: boolean;
    onToggleStats: () => void;
}

export default function PoisoningProcessorOutput({
    videoUrl, intensity, quality,
    poisonedVideoUrl, setPoisonedVideoUrl,
    status, setStatus,
    progressMessage, setProgressMessage,
    progressPercent, setProgressPercent,
    attackResult, setAttackResult,
    error, setError,
    hasStats, showStats, onToggleStats,
}: Props) {

    const [outputDestination, setOutputDestination] = React.useState('');

    const handlePoisoning = async () => {
        if (!videoUrl) { setError('Please select a video first'); return; }
        if (!outputDestination) { setError('Please select an output folder first'); return; }

        setError('');
        setStatus('running');
        setProgressMessage('Starting...');
        setProgressPercent(0);
        setAttackResult(null);
        setPoisonedVideoUrl('');

        try {
            const resultJson: string = await invoke('run_attack', {
                videoPath: videoUrl,
                outputDir: outputDestination,
                intensity, quality,
            });

            const result: AttackResult = JSON.parse(resultJson);
            setAttackResult(result);

            if (result.adv_path) {
                setPoisonedVideoUrl(result.adv_path.replace(/\\/g, '/').trim());
            }

            setStatus('done');
            setProgressPercent(100);
            setProgressMessage(
                result.verified_fooled
                    ? `Protection successful! (${result.total_time.toFixed(1)}s, ${result.attempts} attempts)`
                    : `Completed in ${result.total_time.toFixed(1)}s (protection may be partial)`
            );
        } catch (err: any) {
            setStatus('error');
            setError(typeof err === 'string' ? err : err?.message || 'Unknown error');
            setProgressMessage('');
        }
    };

    const handleSelectOutputFolder = async () => {
        try {
            const selected = await open({
                multiple: false, directory: true,
                defaultPath: outputDestination || undefined,
                title: 'Select Output Folder',
            });
            if (selected) setOutputDestination(String(selected));
        } catch { setError('Failed to open folder dialog'); }
    };

    const isRunning = status === 'running';

    return (
        <React.Fragment>
            <div className="text-lg font-semibold"
                style={{
                    backgroundColor: 'var(--box-primary-color)',
                    width: '100%', padding: 10, textAlign: 'left',
                    flexShrink: 0,
                }}>
                3. Output
            </div>
            <div style={{
                backgroundColor: 'var(--box-secondary-color)',
                width: '100%',
                padding: '10px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                flex: 1,
                minHeight: 0,
            }}>
                {/* Output folder */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <button className="btn px-4 py-2"
                        onClick={handleSelectOutputFolder}
                        disabled={isRunning}
                        style={{
                            borderColor: 'var(--senary-text-color)',
                            borderRadius: '50px', padding: '8px 16px',
                            opacity: isRunning ? 0.5 : 1,
                            fontSize: '0.85rem',
                            flexShrink: 0,
                        }}>
                        Output Destination <RiFolder5Fill size={16} />
                    </button>
                    <div style={{
                        color: 'var(--primary-text-color)',
                        textAlign: 'right',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        marginLeft: 12,
                        fontSize: '0.8rem',
                        flex: 1,
                    }}>
                        {outputDestination || 'No folder selected'}
                    </div>
                </div>

                {/* Progress bar — compact */}
                {isRunning && (
                    <div>
                        <div style={{
                            width: '100%', height: '5px',
                            backgroundColor: 'rgba(255,255,255,0.08)',
                            borderRadius: '3px', overflow: 'hidden',
                            marginBottom: '4px',
                        }}>
                            <div style={{
                                height: '100%',
                                width: `${progressPercent}%`,
                                background: 'linear-gradient(90deg, #8b5cf6, #3b82f6)',
                                borderRadius: '3px',
                                transition: 'width 0.3s ease',
                            }} />
                        </div>
                        <div style={{
                            display: 'flex', justifyContent: 'space-between',
                            fontSize: '0.72rem', color: 'var(--septenary-text-color)',
                        }}>
                            <span>{progressMessage || 'Processing...'}</span>
                            <span style={{ fontWeight: 600 }}>{Math.round(progressPercent)}%</span>
                        </div>
                    </div>
                )}

                {/* Done message — compact */}
                {status === 'done' && (
                    <div style={{ color: '#4ade80', fontSize: '0.78rem' }}>
                        {progressMessage}
                    </div>
                )}

                {/* Error — compact */}
                {(status === 'error' || error) && status !== 'running' && (
                    <div style={{
                        color: '#f87171', fontSize: '0.78rem',
                        maxHeight: '40px', overflow: 'auto',
                    }}>
                        {error}
                    </div>
                )}

                {/* Buttons row */}
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                }}>
                    <div>
                        {hasStats && (
                            <button
                                onClick={onToggleStats}
                                style={{
                                    background: showStats
                                        ? 'linear-gradient(135deg, #3b82f6, #8b5cf6)' : 'none',
                                    border: showStats ? 'none' : '1px solid rgba(255,255,255,0.15)',
                                    borderRadius: '50px',
                                    color: showStats ? '#fff' : 'var(--septenary-text-color)',
                                    fontSize: '0.78rem',
                                    padding: '8px 16px',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s ease',
                                    fontWeight: 500,
                                }}
                            >
                                {showStats ? 'Hide Predictions' : 'Show Predictions'}
                            </button>
                        )}
                    </div>

                    <button className="btn px-4 py-2 gradient-btn-start-processing"
                        onClick={handlePoisoning}
                        disabled={isRunning}
                        style={{
                            borderColor: 'var(--senary-text-color)',
                            borderRadius: '50px',
                            padding: '8px 20px',
                            opacity: isRunning ? 0.5 : 1,
                            cursor: isRunning ? 'not-allowed' : 'pointer',
                        }}>
                        <div style={{ color: 'var(--primary-text-color)', fontSize: '0.85rem' }}>
                            {isRunning ? 'Processing...' : 'Start Process'}
                        </div>
                    </button>
                </div>
            </div>
        </React.Fragment>
    );
}

// 'use client'

// import { RiFolder5Fill } from "@remixicon/react";
// import React from "react";
// import { open } from '@tauri-apps/plugin-dialog';
// import { invoke } from "@tauri-apps/api/core";
// import type { AttackResult, ProcessingStatus } from "./PoisoningProcessor";


// interface Props {
//     videoUrl: string;
//     intensity: number;
//     quality: number;
//     poisonedVideoUrl: string;
//     setPoisonedVideoUrl: (url: string) => void;
//     status: ProcessingStatus;
//     setStatus: (status: ProcessingStatus) => void;
//     progressMessage: string;
//     setProgressMessage: (msg: string) => void;
//     attackResult: AttackResult | null;
//     setAttackResult: (result: AttackResult | null) => void;
//     error: string;
//     setError: (error: string) => void;
//     hasStats: boolean;
//     showStats: boolean;
//     onToggleStats: () => void;
// }

// export default function PoisoningProcessorOutput({
//     videoUrl,
//     intensity,
//     quality,
//     poisonedVideoUrl,
//     setPoisonedVideoUrl,
//     status,
//     setStatus,
//     progressMessage,
//     setProgressMessage,
//     attackResult,
//     setAttackResult,
//     error,
//     setError,
//     hasStats,
//     showStats,
//     onToggleStats,
// }: Props) {

//     const [outputDestination, setOutputDestination] = React.useState('');

//     const handlePoisoning = async () => {
//         if (!videoUrl) {
//             setError('Please select a video first');
//             return;
//         }
//         if (!outputDestination) {
//             setError('Please select an output folder first');
//             return;
//         }

//         setError('');
//         setStatus('running');
//         setProgressMessage('Starting attack...');
//         setAttackResult(null);
//         setPoisonedVideoUrl('');

//         try {
//             const resultJson: string = await invoke('run_attack', {
//                 videoPath: videoUrl,
//                 outputDir: outputDestination,
//                 intensity: intensity,
//                 quality: quality,
//             });

//             const result: AttackResult = JSON.parse(resultJson);
//             setAttackResult(result);

//             if (result.adv_path) {
//                 const cleanPath = result.adv_path.replace(/\\/g, '/').trim();
//                 setPoisonedVideoUrl(cleanPath);
//             }

//             setStatus('done');
//             setProgressMessage(
//                 result.verified_fooled
//                     ? `Protection successful! (${result.total_time.toFixed(1)}s, ${result.attempts} attempts)`
//                     : `Completed in ${result.total_time.toFixed(1)}s (protection may be partial)`
//             );
//         } catch (err: any) {
//             setStatus('error');
//             const msg = typeof err === 'string' ? err : err?.message || 'Unknown error';
//             setError(msg);
//             setProgressMessage('');
//         }
//     };

//     const handleSelectOutputFolder = async () => {
//         try {
//             const selected = await open({
//                 multiple: false,
//                 directory: true,
//                 defaultPath: outputDestination || undefined,
//                 title: 'Select Output Folder for Poisoned Videos',
//             });
//             if (selected) {
//                 setOutputDestination(String(selected));
//             }
//         } catch (err) {
//             setError('Failed to open folder dialog');
//         }
//     };

//     const isRunning = status === 'running';

//     return (
//         <React.Fragment>
//             <div className="text-lg font-semibold"
//                 style={{
//                     backgroundColor: 'var(--box-primary-color)',
//                     width: '100%',
//                     padding: 10,
//                     textAlign: 'left'
//                 }}>
//                 3. Output
//             </div>
//             <div className="flex flex-col justify-center gap-3 p-4"
//                 style={{
//                     backgroundColor: 'var(--box-secondary-color)',
//                     width: '100%',
//                     height: '100%',
//                 }}>
//                 <div className="w-full">
//                     {/* Output folder selector */}
//                     <div className="flex justify-between items-center" style={{ padding: '0 0 8px 0' }}>
//                         <button className="btn px-4 py-2"
//                             onClick={handleSelectOutputFolder}
//                             disabled={isRunning}
//                             style={{
//                                 borderColor: 'var(--senary-text-color)',
//                                 borderRadius: '50px',
//                                 padding: 20,
//                                 opacity: isRunning ? 0.5 : 1,
//                             }}>
//                             Output Destination <RiFolder5Fill size={20} />
//                         </button>
//                         <div style={{
//                             color: 'var(--primary-text-color)',
//                             textAlign: 'left',
//                             textWrap: 'wrap',
//                             maxWidth: '60%',
//                             overflow: 'hidden',
//                             marginLeft: 20,
//                             fontSize: '0.85rem',
//                         }}>
//                             {outputDestination || 'No folder selected'}
//                         </div>
//                     </div>

//                     {/* Status area */}
//                     {(status !== 'idle' || error) && (
//                         <div style={{ padding: '4px 0 8px 0' }}>
//                             {isRunning && (
//                                 <div className="flex items-center gap-2">
//                                     <span className="loading loading-spinner loading-sm"
//                                         style={{ color: 'var(--primary-text-color)' }} />
//                                     <span style={{
//                                         color: 'var(--septenary-text-color)',
//                                         fontSize: '0.85rem',
//                                     }}>
//                                         {progressMessage || 'Processing...'}
//                                     </span>
//                                 </div>
//                             )}
//                             {status === 'done' && (
//                                 <div style={{ color: '#4ade80', fontSize: '0.85rem' }}>
//                                     {progressMessage}
//                                 </div>
//                             )}
//                             {(status === 'error' || error) && (
//                                 <div style={{
//                                     color: '#f87171',
//                                     fontSize: '0.85rem',
//                                     maxHeight: '60px',
//                                     overflow: 'auto',
//                                 }}>
//                                     {error}
//                                 </div>
//                             )}
//                         </div>
//                     )}

//                     {/* Buttons row: Show Predictions + Start Process */}
//                     <div style={{
//                         display: 'flex',
//                         justifyContent: 'space-between',
//                         alignItems: 'center',
//                         paddingTop: '4px',
//                     }}>
//                         {/* Show Predictions button — only when stats available */}
//                         <div>
//                             {hasStats && (
//                                 <button
//                                     onClick={onToggleStats}
//                                     style={{
//                                         background: showStats
//                                             ? 'linear-gradient(135deg, #3b82f6, #8b5cf6)'
//                                             : 'none',
//                                         border: showStats
//                                             ? 'none'
//                                             : '1px solid rgba(255,255,255,0.15)',
//                                         borderRadius: '50px',
//                                         color: showStats ? '#fff' : 'var(--septenary-text-color)',
//                                         fontSize: '0.8rem',
//                                         padding: '10px 20px',
//                                         cursor: 'pointer',
//                                         transition: 'all 0.2s ease',
//                                         fontWeight: 500,
//                                     }}
//                                 >
//                                     {showStats ? 'Hide Predictions' : 'Show Predictions'}
//                                 </button>
//                             )}
//                         </div>

//                         {/* Start Process button */}
//                         <button className="btn px-4 py-2 gradient-btn-start-processing"
//                             onClick={handlePoisoning}
//                             disabled={isRunning}
//                             style={{
//                                 borderColor: 'var(--senary-text-color)',
//                                 borderRadius: '50px',
//                                 padding: 20,
//                                 opacity: isRunning ? 0.5 : 1,
//                                 cursor: isRunning ? 'not-allowed' : 'pointer',
//                             }}>
//                             <div style={{ color: 'var(--primary-text-color)' }}>
//                                 {isRunning ? 'Processing...' : 'Start Process'}
//                             </div>
//                         </button>
//                     </div>
//                 </div>
//             </div>
//         </React.Fragment>
//     );
// }