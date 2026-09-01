import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';

import { onboardingApi } from '../../api/onboardingApi.js';

const HEARTBEAT_INTERVAL_MS = 5000;
const SEEK_GRACE_SECONDS = 1.5;

function formatSeconds(value) {
  const total = Math.max(0, Math.ceil(Number(value) || 0));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

export default function VerifiedTrainingVideo({
  task,
  onAssignmentUpdate,
  onError,
}) {
  const videoRef = useRef(null);
  const requestPendingRef = useRef(false);
  const endedPendingRef = useRef(false);
  const [progress, setProgress] = useState(
    task.video_progress || {},
  );

  useEffect(() => {
    setProgress(task.video_progress || {});
  }, [task.video_progress]);

  const syncProgress = useCallback(async (event) => {
    const video = videoRef.current;
    if (!video) return;
    if (requestPendingRef.current) {
      if (event === 'ended') endedPendingRef.current = true;
      return;
    }

    requestPendingRef.current = true;
    try {
      const response = await onboardingApi.videoProgress(
        task.id,
        {
          event,
          position_seconds: Number(video.currentTime || 0),
        },
      );
      const nextProgress = response.data.video_progress || {};
      setProgress(nextProgress);
      onAssignmentUpdate?.(response.data);

      if (
        nextProgress.seek_blocked
        && Number(video.currentTime || 0)
          > Number(nextProgress.resume_position_seconds || 0)
            + SEEK_GRACE_SECONDS
      ) {
        video.currentTime = Number(
          nextProgress.resume_position_seconds || 0,
        );
      }
    } catch (err) {
      onError?.(
        err.error?.message
        || 'Unable to save verified video progress',
      );
      video.pause();
    } finally {
      requestPendingRef.current = false;
      if (endedPendingRef.current) {
        endedPendingRef.current = false;
        syncProgress('ended');
      }
    }
  }, [onAssignmentUpdate, onError, task.id]);

  useEffect(() => {
    const pauseForInactivity = () => {
      const video = videoRef.current;
      if (video && !video.paused) video.pause();
    };

    const handleVisibility = () => {
      if (document.hidden) pauseForInactivity();
    };

    document.addEventListener(
      'visibilitychange',
      handleVisibility,
    );
    window.addEventListener('blur', pauseForInactivity);

    return () => {
      document.removeEventListener(
        'visibilitychange',
        handleVisibility,
      );
      window.removeEventListener('blur', pauseForInactivity);
    };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const video = videoRef.current;
      if (
        !video
        || video.paused
        || video.ended
        || document.hidden
        || !document.hasFocus()
      ) {
        return;
      }
      syncProgress('heartbeat');
    }, HEARTBEAT_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [syncProgress]);

  const resumePosition = Number(
    progress.resume_position_seconds || 0,
  );
  const duration = Number(progress.duration_seconds || 0);
  const verified = Number(progress.verified_seconds || 0);
  const remaining = Number(progress.remaining_seconds || 0);
  const ready = Boolean(progress.completion_ready);

  return (
    <div className="mt-3 max-w-xl">
      <video
        ref={videoRef}
        className="w-full rounded-lg bg-slate-950"
        controls
        controlsList="nodownload"
        disablePictureInPicture
        preload="metadata"
        src={onboardingApi.resourceContentUrl(
          task.resource.id,
          task.tenant_id,
        )}
        onLoadedMetadata={(event) => {
          const video = event.currentTarget;
          video.playbackRate = 1;
          if (
            resumePosition > 0
            && resumePosition < video.duration
          ) {
            video.currentTime = resumePosition;
          }
        }}
        onPlay={(event) => {
          const video = event.currentTarget;
          if (document.hidden || !document.hasFocus()) {
            video.pause();
            return;
          }
          video.playbackRate = 1;
          syncProgress('start');
        }}
        onPause={(event) => {
          if (!event.currentTarget.ended) {
            syncProgress('pause');
          }
        }}
        onEnded={() => syncProgress('ended')}
        onSeeking={(event) => {
          const video = event.currentTarget;
          if (
            !ready
            && video.currentTime
              > resumePosition + SEEK_GRACE_SECONDS
          ) {
            video.currentTime = resumePosition;
          }
        }}
        onRateChange={(event) => {
          if (event.currentTarget.playbackRate !== 1) {
            event.currentTarget.playbackRate = 1;
          }
        }}
      >
        Your browser does not support training video playback.
      </video>

      <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
          <span>
            Verified {formatSeconds(verified)}
            {' / '}
            {formatSeconds(duration)}
          </span>
          <span>
            {ready
              ? 'Viewing requirement complete'
              : `${formatSeconds(remaining)} remaining`}
          </span>
        </div>
        <div
          className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200"
          role="progressbar"
          aria-label="Verified training progress"
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow={Math.min(
            100,
            Number(progress.verified_percent || 0),
          )}
        >
          <div
            className="h-full rounded-full bg-blue-600 transition-[width]"
            style={{
              width: `${Math.min(
                100,
                Number(progress.verified_percent || 0),
              )}%`,
            }}
          />
        </div>
        <p className="mt-2 text-xs text-slate-500">
          {ready
            ? 'Training viewing verified. Acknowledge to finish the task.'
            : 'Training in progress — watch the full video to unlock completion. Seeking ahead and background playback do not count.'}
        </p>
      </div>
    </div>
  );
}
