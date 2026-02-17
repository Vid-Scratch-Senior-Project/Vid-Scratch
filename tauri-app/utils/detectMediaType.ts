export default function detectMediaType(url: string) {
    const mediaPatterns = {
        youtube: /youtube\.com|youtu\.be/i,
        tiktok: /tiktok\.com/i,
        video: /\.(mp4|webm|ogg|mov|avi|wmv|flv|mkv)$/i,
        image: /\.(jpg|jpeg|png|gif|webp|avif|svg|bmp|tiff|ico)$/i,
        imageServices: /picsum\.photos|unsplash\.com|via\.placeholder\.com|placeimg\.com|lorempixel\.com|fakeimg\.pl|dummyimage\.com/i
    };

    if (mediaPatterns.youtube.test(url)) return 'youtube';
    if (mediaPatterns.tiktok.test(url)) return 'tiktok';
    if (mediaPatterns.video.test(url)) return 'video';
    if (mediaPatterns.image.test(url) || mediaPatterns.imageServices.test(url)) return 'image';

    return 'unknown';
}