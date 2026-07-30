export function createPolling({
    refresh,
    isHidden = () => document.hidden,
    setTimeoutImpl = window.setTimeout.bind(window),
    clearTimeoutImpl = window.clearTimeout.bind(window),
    visibleDelay = 1000,
    hiddenDelay = 4000,
}) {
    let handle = null;
    let running = false;
    let stopped = true;

    function schedule() {
        if (stopped) {
            return;
        }
        clearTimeoutImpl(handle);
        handle = setTimeoutImpl(run, isHidden() ? hiddenDelay : visibleDelay);
    }

    async function run() {
        if (stopped || running) {
            return;
        }
        running = true;
        try {
            await refresh();
        } finally {
            running = false;
            schedule();
        }
    }

    return {
        start({immediate = true} = {}) {
            stopped = false;
            if (immediate) {
                void run();
            } else {
                schedule();
            }
        },
        refresh: run,
        reschedule: schedule,
        stop() {
            stopped = true;
            clearTimeoutImpl(handle);
            handle = null;
        },
    };
}
