'use client'

import { RiFolder5Fill } from "@remixicon/react";
import React from "react";
import { open } from '@tauri-apps/plugin-dialog';


export default function PoisoningProcessorOutput({ videoUrl, intensity, quality, poisonedVideoUrl, setPoisonedVideoUrl }: { videoUrl: string, intensity: number, quality: number, poisonedVideoUrl: string, setPoisonedVideoUrl: (url: string) => void }) {

    const [error, setError] = React.useState('');
    const [outputDestination, setOutputDestination] = React.useState('');

    const handlePoisoning = () => {
        // Initiate poisoning process
        // generateIDHash_datetime_Filename.mp4
        setPoisonedVideoUrl("/poisoned_" + videoUrl);
    };

    const handleSelectOutputFolder = async () => {
        try {
            const selected = await open({
                multiple: false,
                directory: true,
                defaultPath: outputDestination || undefined, // Start from last selected folder
                title: 'Select Output Folder for Poisoned Videos', // Dialog title
            });

            if (selected) {
                setOutputDestination(String(selected));
            }
        } catch (err) {
            setError('Failed to open folder dialog');
        }
    };

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
            <div className="flex flex-col justify-center gap-4 p-4"
                style={{
                    backgroundColor: 'var(--box-secondary-color)',
                    width: '100%',
                    height: '100%',
                }}>
                <div className="w-full">
                    <div className="flex justify-between p-4">
                        <button className="btn px-4 py-2"
                            onClick={handleSelectOutputFolder}
                            style={{
                                borderColor: 'var(--senary-text-color)',
                                borderRadius: '50px',
                                padding: 20,
                            }}>
                            Output Destination <RiFolder5Fill size={20} />
                        </button>
                        <div
                            style={{
                                color: 'var(--primary-text-color)',
                                textAlign: 'left',
                                textWrap: 'wrap',
                                maxWidth: '60%',
                                overflow: 'hidden',
                                marginLeft: 20
                            }}>
                            {outputDestination ?? 'No folder selected'}
                            {error ?? ''}
                        </div>
                    </div>

                    <div
                        style={{
                            width: '100%',
                            display: 'flex',
                            justifyContent: 'flex-end'
                        }}>
                        <button className="btn px-4 py-2 gradient-btn-start-processing"
                        onClick={handlePoisoning}
                        style={{
                            borderColor: 'var(--senary-text-color)',
                            borderRadius: '50px',
                            padding: 20,
                            alignSelf: 'end'
                        }}>
                        <div
                            style={{
                                color: 'var(--primary-text-color)',
                            }}>
                            Start Process
                        </div>
                    </button>
                    </div>
                    
                </div>
            </div>
        </React.Fragment>
    )
}