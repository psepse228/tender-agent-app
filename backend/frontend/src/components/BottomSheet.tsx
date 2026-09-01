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
            // Elastic resistance is applied to the *reported* drag offset
            // too, not just the visual rubber-band -- 0.6 here meant a
            // real ~400px finger swipe only ever produced an offset well
            // under the 120px close threshold below, so the swipe visibly
            // moved the sheet but could never actually close it (UI-audit
            // #3). 0.92 keeps a token bit of resistance (so it still reads
            // as "grabbing the sheet", not 1:1 pass-through) while letting
            // a real swipe's offset actually cross the threshold.
            dragElastic={{ top: 0, bottom: 0.92 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 80 || info.velocity.y > 400) onClose();
            }}
          >
            <div className="sheet-handle" />
            <button className="sheet-close-btn press" onClick={onClose} title="Закрыть" aria-label="Закрыть">
              <CloseIcon />
            </button>
            <div className="sheet-body">{children}</div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
