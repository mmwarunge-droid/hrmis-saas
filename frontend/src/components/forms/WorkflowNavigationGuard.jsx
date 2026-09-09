import { useContext, useEffect } from 'react';
import { UNSAFE_DataRouterContext, useBlocker } from 'react-router-dom';
import { hasUnsavedWork, requestWorkflowExit } from '../../utils/formFeedback.js';

function NavigationBlocker() {
  const blocker = useBlocker(() => hasUnsavedWork());
  useEffect(() => {
    if (blocker.state === 'blocked') requestWorkflowExit(() => blocker.proceed(), () => blocker.reset());
  }, [blocker]);
  return null;
}
export default function WorkflowNavigationGuard() {
  const router = useContext(UNSAFE_DataRouterContext);
  return router ? <NavigationBlocker /> : null;
}
