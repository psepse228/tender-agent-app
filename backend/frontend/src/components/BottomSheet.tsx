import { AnimatePresence, motion } from 'motion/react';
import type { ReactNode } from 'react';
import { CloseIcon } from './icons';

interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

/** The Тендеры screen's swipe-down-to-dismiss detail sheet (renderStatsHtml
 * in the old vanilla frontend). Framer Motion replaces the old CSS
 * transform/opacity transitions with the same easing curve. */
export function BottomSheet({ open, onClose, children }: BottomSheetProps) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="sheet-overlay"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          />
          <motion.div
            className="sheet"
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 32, stiffness: 320 }}
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.6 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 120 || info.velocity.y > 600) onClose();
            }}
          >
            <div className="sheet-handle" />
            <button className="sheet-close-btn" onClick={onClose} title="Закрыть" aria-label="Закрыть">
              <CloseIcon />
            </button>
            <div className="sheet-body">{children}</div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
