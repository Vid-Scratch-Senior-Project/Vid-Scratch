'use client'
import { open } from '@tauri-apps/plugin-dialog';
import detectMediaType from "../../utils/detectMediaType";
import React from "react";
import { useState } from "react";

export default function PoisoningProcessorInput({ filepath, setFilepath }: { filepath: string, setFilepath: (filename: string) => void }) {
    const [error, setError] = useState('');
    const [isUploading, setIsUploading] = useState(false);

    // const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB in bytes

    const validateFile = (filepath: string): boolean => {
        // Check file size
        // if (file.size > MAX_FILE_SIZE) {
        //     setError('File size exceeds 100MB limit');
        //     return false;
        // }

        // Check media type
        const mediaType = detectMediaType(filepath);
        if (mediaType !== 'video') {
            setError('Only video files are supported');
            return false;
        }

        // Clear any previous errors
        setError('');
        return true;
    };

    const handleFileSelect = async () => {
        try {
            setIsUploading(true);

            // Open file dialog using Tauri
            const selected = await open({
                multiple: false,
                filters: [{
                    name: 'Video',
                    extensions: ['mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm']
                }]
            });

            if (selected && !Array.isArray(selected)) {

                if (validateFile(selected)) {
                    setFilepath(selected);
                }
            }
        } catch (err) {
            setError('Failed to open file dialog');
            console.error(err);
        } finally {
            setIsUploading(false);
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
                1.  Select video to poison
            </div>
            <div className="flex items-center gap-4 p-4"
                style={{
                    backgroundColor: 'var(--box-secondary-color)',
                    width: '100%',
                }}>
                <button
                    onClick={handleFileSelect}
                    disabled={isUploading}
                    className="btn px-4 py-2"
                    style={{
                        borderColor: 'var(--senary-text-color)',
                        borderRadius: '50px',
                        padding: 20,
                    }}
                >
                    {isUploading ? 'Opening...' : 'Select Video'}
                </button>

                <div
                    style={{
                        textAlign: 'left',
                        display: 'flex',
                        wordWrap: 'break-word',
                        flexWrap: 'wrap',
                        width: '80%'
                    }}>

                    {filepath && (
                        <p className="text-sm text-gray-400">
                            Selected video: {filepath}
                        </p>
                    )}

                    {error && (
                        <p className="text-sm text-red-500">
                            {error}
                        </p>
                    )}
                </div>
            </div>
        </React.Fragment>
    )
}