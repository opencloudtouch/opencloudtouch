/**
 * Restore Wizard Hooks
 *
 * TanStack Query mutations for restore wizard API operations.
 */

import { useMutation } from "@tanstack/react-query";
import {
  scanBackups,
  executeRestore,
  type ScanBackupsRequest,
  type ScanBackupsResponse,
  type RestoreWizardRequest,
  type RestoreWizardResponse,
} from "../api/restore";

export function useScanBackups() {
  return useMutation<ScanBackupsResponse, Error, ScanBackupsRequest>({
    mutationFn: scanBackups,
  });
}

export function useExecuteRestore() {
  return useMutation<RestoreWizardResponse, Error, RestoreWizardRequest>({
    mutationFn: executeRestore,
  });
}
