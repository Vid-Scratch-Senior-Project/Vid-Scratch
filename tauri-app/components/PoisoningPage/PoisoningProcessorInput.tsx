'use client'

import detectMediaType from "../../utils/detectMediaType";
import React from "react";
import { useRef, useState } from "react";

export default function PoisoningProcessorInput({filepath, setFilepath}: {filepath: string, setFilepath: (filename: string) => void}) {
    const [error, setError] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const hiddenFileInput = useRef<HTMLInputElement>(null);

    // const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB in bytes

    const validateFile = (file: File): boolean => {
        // Check file size
        // if (file.size > MAX_FILE_SIZE) {
        //     setError('File size exceeds 100MB limit');
        //     return false;
        // }

        // Check media type
        const mediaType = detectMediaType(file.name);
        if (mediaType !== 'video') {
            setError('Only video files are supported');
            return false;
        }

        // Clear any previous errors
        setError('');
        return true;
    };

    const handleFileInputChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];

        if (!file) return;

        if (validateFile(file)) {
            setFilepath(file.path);
        }
    };

    const handleClick = () => {
        hiddenFileInput.current?.click();
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
                <input
                    type="file"
                    ref={hiddenFileInput}
                    onChange={handleFileInputChange}
                    accept="video/*"
                    className="hidden"
                />

                <button
                    onClick={handleClick}
                    disabled={isUploading}
                    className="btn px-4 py-2"
                    style={{
                        borderColor: 'var(--senary-text-color)',
                        borderRadius: '50px',
                        padding: 20,
                    }}
                >
                    {isUploading ? 'Uploading...' : 'Select Video'}
                </button>

                <div>

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