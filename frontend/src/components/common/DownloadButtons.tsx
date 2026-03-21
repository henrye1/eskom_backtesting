import { getDownloadUrl } from '../../api/client';

interface Props {
  jobId: string;
  windowSize: number;
}

export default function DownloadButtons({ jobId, windowSize }: Props) {
  return (
    <div className="flex gap-3 mb-6">
      <a href={getDownloadUrl(jobId, 'multi-scenario-excel')}
        className="px-4 py-2 bg-green-600 text-white text-sm rounded hover:bg-green-700">
        Multi-Scenario Excel
      </a>
      <a href={`/api/analysis/${jobId}/download/single-excel/${windowSize}`}
        className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">
        {windowSize}m Excel
      </a>
      <a href={getDownloadUrl(jobId, 'html-dashboard')}
        className="px-4 py-2 bg-purple-600 text-white text-sm rounded hover:bg-purple-700">
        HTML Dashboard
      </a>
    </div>
  );
}
