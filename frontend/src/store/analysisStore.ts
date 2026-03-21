import { create } from 'zustand';

interface AnalysisState {
  fileId: string | null;
  fileName: string | null;
  jobId: string | null;
  status: 'idle' | 'uploading' | 'running' | 'completed' | 'failed';
  error: string | null;
  selectedWindow: number;
  params: {
    windowSizes: number[];
    discountRate: number;
    lgdCap: number | null;
    ciPercentile: number;
    maxTid: number;
    storeDetail: boolean;
  };
  setFileId: (id: string, name: string) => void;
  setJobId: (id: string) => void;
  setStatus: (s: AnalysisState['status']) => void;
  setError: (e: string | null) => void;
  setSelectedWindow: (w: number) => void;
  updateParams: (p: Partial<AnalysisState['params']>) => void;
  reset: () => void;
}

const defaultParams = {
  windowSizes: [12, 18, 24, 30, 36, 42, 48, 54, 60],
  discountRate: 0.15,
  lgdCap: null as number | null,
  ciPercentile: 0.75,
  maxTid: 60,
  storeDetail: false,
};

export const useAnalysisStore = create<AnalysisState>((set) => ({
  fileId: null,
  fileName: null,
  jobId: null,
  status: 'idle',
  error: null,
  selectedWindow: 60,
  params: { ...defaultParams },
  setFileId: (id, name) => set({ fileId: id, fileName: name }),
  setJobId: (id) => set({ jobId: id, status: 'running' }),
  setStatus: (s) => set({ status: s }),
  setError: (e) => set({ error: e, status: 'failed' }),
  setSelectedWindow: (w) => set({ selectedWindow: w }),
  updateParams: (p) => set((state) => ({ params: { ...state.params, ...p } })),
  reset: () => set({ fileId: null, fileName: null, jobId: null, status: 'idle', error: null }),
}));
