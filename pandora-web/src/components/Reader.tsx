import { useState } from 'react';

export const Reader = ({ images, onClose }: { images: string[], onClose: () => void }) => {
  const [viewMode, setViewMode] = useState<'paged' | 'scroll'>('paged');
  const [currentPage, setCurrentPage] = useState(0);

  const handlePrev = () => {
    setCurrentPage((prev) => Math.max(0, prev - 1));
  };

  const handleNext = () => {
    setCurrentPage((prev) => Math.min(images.length - 1, prev + 1));
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#000', zIndex: 1000, overflowY: viewMode === 'scroll' ? 'auto' : 'hidden' }}>
      <div style={{ position: 'fixed', top: '10px', right: '10px', zIndex: 1001 }}>
        <button onClick={() => setViewMode(viewMode === 'paged' ? 'scroll' : 'paged')}>Toggle Mode</button>
        <button onClick={onClose} style={{ marginLeft: '10px' }}>Exit</button>
      </div>
      {viewMode === 'paged' ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', position: 'relative' }}>
          {images.length > 0 && (
            <>
              <div 
                style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '50%', cursor: 'w-resize' }} 
                onClick={handlePrev} 
              />
              <div 
                style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: '50%', cursor: 'e-resize' }} 
                onClick={handleNext} 
              />
              <img src={images[currentPage]} style={{ maxHeight: '100%', maxWidth: '100%' }} />
              <div style={{ position: 'absolute', bottom: '20px', color: 'white', background: 'rgba(0,0,0,0.5)', padding: '5px 10px', borderRadius: '5px', pointerEvents: 'none' }}>
                {currentPage + 1} / {images.length}
              </div>
            </>
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          {images.map((url, i) => <img key={i} src={url} style={{ maxWidth: '100%', marginBottom: '10px' }} />)}
        </div>
      )}
    </div>
  );
};
