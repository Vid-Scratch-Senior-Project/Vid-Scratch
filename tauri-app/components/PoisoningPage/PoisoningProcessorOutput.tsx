// 'use client'

// import { RiFolder5Fill } from "@remixicon/react";
// import React from "react";
// import { open } from '@tauri-apps/plugin-dialog';
// import { invoke } from "@tauri-apps/api/core";
// import type { AttackResult, ProcessingStatus } from "./PoisoningProcessor";


// interface PoisoningProcessorOutputProps {
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
// }: PoisoningProcessorOutputProps) {

//     const [outputDestination, setOutputDestination] = React.useState('');

//     const handlePoisoning = async () => {
//         // Validate
//         if (!videoUrl) {
//             setError('Please select a video first');
//             return;
//         }
//         if (!outputDestination) {
//             setError('Please select an output folder first');
//             return;
//         }

//         // Reset state
//         setError('');
//         setStatus('running');
//         setProgressMessage('Starting attack...');
//         setAttackResult(null);
//         setPoisonedVideoUrl('');

//         try {
//             // Call Tauri backend command
//             const resultJson: string = await invoke('run_attack', {
//                 videoPath: videoUrl,
//                 outputDir: outputDestination,
//                 intensity: intensity,
//                 quality: quality,
//                 pythonPath: null,  // uses "python" by default
//             });

//             // Parse JSON result from attack.py
//             const result: AttackResult = JSON.parse(resultJson);
//             setAttackResult(result);

//             if (result.adv_path) {
//                 setPoisonedVideoUrl(result.adv_path);
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
//             <div className="flex flex-col justify-center gap-4 p-4"
//                 style={{
//                     backgroundColor: 'var(--box-secondary-color)',
//                     width: '100%',
//                     height: '100%',
//                 }}>
//                 <div className="w-full">
//                     <div className="flex justify-between p-4">
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
//                         <div
//                             style={{
//                                 color: 'var(--primary-text-color)',
//                                 textAlign: 'left',
//                                 textWrap: 'wrap',
//                                 maxWidth: '60%',
//                                 overflow: 'hidden',
//                                 marginLeft: 20
//                             }}>
//                             {outputDestination || 'No folder selected'}
//                         </div>
//                     </div>

//                     {/* Progress / Status area */}
//                     {(status !== 'idle' || error) && (
//                         <div className="px-4 pb-2">
//                             {isRunning && (
//                                 <div className="flex items-center gap-2">
//                                     <span className="loading loading-spinner loading-sm"
//                                         style={{ color: 'var(--primary-text-color)' }}
//                                     />
//                                     <span style={{
//                                         color: 'var(--septenary-text-color)',
//                                         fontSize: '0.85rem',
//                                     }}>
//                                         {progressMessage || 'Processing...'}
//                                     </span>
//                                 </div>
//                             )}

//                             {status === 'done' && (
//                                 <div style={{
//                                     color: '#4ade80',
//                                     fontSize: '0.85rem',
//                                 }}>
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

//                             {/* Attack result summary */}
//                             {status === 'done' && attackResult && (
//                                 <div style={{
//                                     fontSize: '0.75rem',
//                                     color: 'var(--septenary-text-color)',
//                                     marginTop: '4px',
//                                 }}>
//                                     Original: {attackResult.orig_pred_name} ({(attackResult.orig_confidence * 100).toFixed(1)}%)
//                                     {' → '}
//                                     Poisoned: {attackResult.verified_pred_name} ({(attackResult.adv_confidence * 100).toFixed(1)}%)
//                                     {' | '}
//                                     Frames poisoned: {attackResult.frames_poisoned}/{attackResult.total_frames}
//                                 </div>
//                             )}
//                         </div>
//                     )}

//                     <div
//                         style={{
//                             width: '100%',
//                             display: 'flex',
//                             justifyContent: 'space-between',
//                             alignItems: 'center',
//                             padding: '0 16px',
//                         }}>

//                         {/* Save button — only show when done */}
//                         <div>
//                             {status === 'done' && poisonedVideoUrl && (
//                                 <span style={{
//                                     color: 'var(--septenary-text-color)',
//                                     fontSize: '0.8rem',
//                                 }}>
//                                     Saved to: {poisonedVideoUrl}
//                                 </span>
//                             )}
//                         </div>

//                         <button className="btn px-4 py-2 gradient-btn-start-processing"
//                             onClick={handlePoisoning}
//                             disabled={isRunning}
//                             style={{
//                                 borderColor: 'var(--senary-text-color)',
//                                 borderRadius: '50px',
//                                 padding: 20,
//                                 alignSelf: 'end',
//                                 opacity: isRunning ? 0.5 : 1,
//                                 cursor: isRunning ? 'not-allowed' : 'pointer',
//                             }}>
//                             <div
//                                 style={{
//                                     color: 'var(--primary-text-color)',
//                                 }}>
//                                 {isRunning ? 'Processing...' : 'Start Process'}
//                             </div>
//                         </button>
//                     </div>
//                 </div>
//             </div>
//         </React.Fragment>
//     )
// }

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
    attackResult: AttackResult | null;
    setAttackResult: (result: AttackResult | null) => void;
    error: string;
    setError: (error: string) => void;
    hasStats: boolean;
    showStats: boolean;
    onToggleStats: () => void;
}

export default function PoisoningProcessorOutput({
    videoUrl,
    intensity,
    quality,
    poisonedVideoUrl,
    setPoisonedVideoUrl,
    status,
    setStatus,
    progressMessage,
    setProgressMessage,
    attackResult,
    setAttackResult,
    error,
    setError,
    hasStats,
    showStats,
    onToggleStats,
}: Props) {

    const [outputDestination, setOutputDestination] = React.useState('');

    const handlePoisoning = async () => {
        if (!videoUrl) {
            setError('Please select a video first');
            return;
        }
        if (!outputDestination) {
            setError('Please select an output folder first');
            return;
        }

        setError('');
        setStatus('running');
        setProgressMessage('Starting attack...');
        setAttackResult(null);
        setPoisonedVideoUrl('');

        try {
            const resultJson: string = await invoke('run_attack', {
                videoPath: videoUrl,
                outputDir: outputDestination,
                intensity: intensity,
                quality: quality,
            });

            const result: AttackResult = JSON.parse(resultJson);
            setAttackResult(result);

            if (result.adv_path) {
                const cleanPath = result.adv_path.replace(/\\/g, '/').trim();
                setPoisonedVideoUrl(cleanPath);
            }

            setStatus('done');
            setProgressMessage(
                result.verified_fooled
                    ? `Protection successful! (${result.total_time.toFixed(1)}s, ${result.attempts} attempts)`
                    : `Completed in ${result.total_time.toFixed(1)}s (protection may be partial)`
            );
        } catch (err: any) {
            setStatus('error');
            const msg = typeof err === 'string' ? err : err?.message || 'Unknown error';
            setError(msg);
            setProgressMessage('');
        }
    };

    const handleSelectOutputFolder = async () => {
        try {
            const selected = await open({
                multiple: false,
                directory: true,
                defaultPath: outputDestination || undefined,
                title: 'Select Output Folder for Poisoned Videos',
            });
            if (selected) {
                setOutputDestination(String(selected));
            }
        } catch (err) {
            setError('Failed to open folder dialog');
        }
    };

    const isRunning = status === 'running';

    return (
        <React.Fragment>
            <div className="text-lg font-semibold"
                style={{
                    backgroundColor: 'var(--box-primary-color)',
                    width: '100%',
                    padding: 10,
                    textAlign: 'left'
                }}>
                3. Output
            </div>
            <div className="flex flex-col justify-center gap-3 p-4"
                style={{
                    backgroundColor: 'var(--box-secondary-color)',
                    width: '100%',
                    height: '100%',
                }}>
                <div className="w-full">
                    {/* Output folder selector */}
                    <div className="flex justify-between items-center" style={{ padding: '0 0 8px 0' }}>
                        <button className="btn px-4 py-2"
                            onClick={handleSelectOutputFolder}
                            disabled={isRunning}
                            style={{
                                borderColor: 'var(--senary-text-color)',
                                borderRadius: '50px',
                                padding: 20,
                                opacity: isRunning ? 0.5 : 1,
                            }}>
                            Output Destination <RiFolder5Fill size={20} />
                        </button>
                        <div style={{
                            color: 'var(--primary-text-color)',
                            textAlign: 'left',
                            textWrap: 'wrap',
                            maxWidth: '60%',
                            overflow: 'hidden',
                            marginLeft: 20,
                            fontSize: '0.85rem',
                        }}>
                            {outputDestination || 'No folder selected'}
                        </div>
                    </div>

                    {/* Status area */}
                    {(status !== 'idle' || error) && (
                        <div style={{ padding: '4px 0 8px 0' }}>
                            {isRunning && (
                                <div className="flex items-center gap-2">
                                    <span className="loading loading-spinner loading-sm"
                                        style={{ color: 'var(--primary-text-color)' }} />
                                    <span style={{
                                        color: 'var(--septenary-text-color)',
                                        fontSize: '0.85rem',
                                    }}>
                                        {progressMessage || 'Processing...'}
                                    </span>
                                </div>
                            )}
                            {status === 'done' && (
                                <div style={{ color: '#4ade80', fontSize: '0.85rem' }}>
                                    {progressMessage}
                                </div>
                            )}
                            {(status === 'error' || error) && (
                                <div style={{
                                    color: '#f87171',
                                    fontSize: '0.85rem',
                                    maxHeight: '60px',
                                    overflow: 'auto',
                                }}>
                                    {error}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Buttons row: Show Predictions + Start Process */}
                    <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        paddingTop: '4px',
                    }}>
                        {/* Show Predictions button — only when stats available */}
                        <div>
                            {hasStats && (
                                <button
                                    onClick={onToggleStats}
                                    style={{
                                        background: showStats
                                            ? 'linear-gradient(135deg, #3b82f6, #8b5cf6)'
                                            : 'none',
                                        border: showStats
                                            ? 'none'
                                            : '1px solid rgba(255,255,255,0.15)',
                                        borderRadius: '50px',
                                        color: showStats ? '#fff' : 'var(--septenary-text-color)',
                                        fontSize: '0.8rem',
                                        padding: '10px 20px',
                                        cursor: 'pointer',
                                        transition: 'all 0.2s ease',
                                        fontWeight: 500,
                                    }}
                                >
                                    {showStats ? 'Hide Predictions' : 'Show Predictions'}
                                </button>
                            )}
                        </div>

                        {/* Start Process button */}
                        <button className="btn px-4 py-2 gradient-btn-start-processing"
                            onClick={handlePoisoning}
                            disabled={isRunning}
                            style={{
                                borderColor: 'var(--senary-text-color)',
                                borderRadius: '50px',
                                padding: 20,
                                opacity: isRunning ? 0.5 : 1,
                                cursor: isRunning ? 'not-allowed' : 'pointer',
                            }}>
                            <div style={{ color: 'var(--primary-text-color)' }}>
                                {isRunning ? 'Processing...' : 'Start Process'}
                            </div>
                        </button>
                    </div>
                </div>
            </div>
        </React.Fragment>
    );
}