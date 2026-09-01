import { AnimatePresence, motion } from 'motion/react';

interface BootSplashProps {
  show: boolean;
}

/** The branded loading screen the previous vanilla frontend showed on every
 * cold start (#loader in the old index.html) -- lost entirely in the React
 * rewrite, which just showed a bare blank frame until the shell mounted.
 * First impression matters here: this is the very first thing anyone sees. */
export function BootSplash({ show }: BootSplashProps) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className="boot-splash"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        >
          <motion.div
            className="boot-splash-logo"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.2, 0.7, 0.3, 1] }}
          >
            <motion.div
              className="boot-splash-mark"
              animate={{ boxShadow: ['0 0 20px rgba(56,189,248,.25)', '0 0 34px rgba(56,189,248,.5)', '0 0 20px rgba(56,189,248,.25)'] }}
              transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
            >
              T
            </motion.div>
            <div className="boot-splash-wordmark">Tender Agent</div>
          </motion.div>
          <div className="boot-splash-sub">AI · Анализ тендеров</div>
          <div className="boot-splash-track">
            <motion.div
              className="boot-splash-fill"
              animate={{ x: ['-100%', '20%', '150%'] }}
              transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
