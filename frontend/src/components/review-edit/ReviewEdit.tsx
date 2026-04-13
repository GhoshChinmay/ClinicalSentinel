/* ─── Imports ────────────────────────────────────────────────────────────────────────────── */

import { useState, useEffect, useRef, useMemo } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import { Download, Edit3, AlertCircle, Loader2 } from 'lucide-react';
import api from '@/services/api.service';

import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

/* ─── Initialization & Types ─────────────────────────────────────────────────────────────── */

ModuleRegistry.registerModules([AllCommunityModule]);

export interface ReviewEditProps {
  sessionId: string;
}

export interface ColumnDef {
  field: string;
  sortable: boolean;
  filter: boolean;
}

/* ─── Component ──────────────────────────────────────────────────────────────────────────── */

/**
 * ReviewEdit component displays a spreadsheet-like view of the cleaned dataset,
 * allowing manual edits and exporting.
 *
 * @param {ReviewEditProps} props - The properties for the component.
 * @returns {React.JSX.Element} The rendered spreadsheet interface.
 */
export default function ReviewEdit({ sessionId }: ReviewEditProps): React.JSX.Element {
  const [rowData, setRowData] = useState<Record<string, unknown>[]>([]);
  const [totalRows, setTotalRows] = useState<number>(0);
  const [columnDefs, setColumnDefs] = useState<ColumnDef[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const gridRef = useRef<AgGridReact>(null);

  useEffect(() => {
    if (!sessionId) return;

    const fetchData = async () => {
      try {
        setIsLoading(true);
        const res = await api.get(`/api/data/${sessionId}?is_cleaned=true`);
        const data = res.data.data;
        const total = res.data.total_rows || data.length;

        if (data.length > 0) {
          setColumnDefs(
            Object.keys(data[0]).map((key) => ({
              field: key,
              sortable: true,
              filter: true,
            }))
          );
          setRowData(data);
          setTotalRows(total);
        } else {
          setErrorMsg(
            'No cleaned data available. Complete the Cleaning step first, or note that your cleaning method may have removed all rows.'
          );
        }
      } catch (err: unknown) {
        const axiosErr = err as {
          response?: { data?: { error?: string; detail?: string } };
          message?: string;
        };
        const detail =
          axiosErr.response?.data?.error ||
          axiosErr.response?.data?.detail ||
          axiosErr.message ||
          'Failed to load dataset.';
        setErrorMsg(`Could not load the dataset: ${detail}`);
        console.error('ReviewEdit: Failed to load clean data', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [sessionId]);

  const defaultColDef = useMemo(
    () => ({ flex: 1, minWidth: 120, resizable: true, editable: true }),
    []
  );

  const handleDownload = () => {
    gridRef.current?.api.exportDataAsCsv({ fileName: 'DataSentinel_Cleaned.csv' });
  };

  if (isLoading) {
    return (
      <div className="w-full mt-6 flex flex-col items-center justify-center h-64 border border-neutral-800 rounded-2xl bg-[#0A0A0A]">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500 mb-4" />
        <p className="text-neutral-400">Loading dataset for review...</p>
      </div>
    );
  }

  if (errorMsg) {
    return (
      <div className="w-full mt-6 bg-red-500/10 border border-red-900/50 p-6 rounded-2xl flex items-start text-red-400">
        <AlertCircle className="w-6 h-6 mr-3 shrink-0" />
        <div>
          <h3 className="font-bold text-lg mb-1">Data Load Failed</h3>
          <p className="text-sm">{errorMsg}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full mt-6">
      <div className="flex justify-between items-center bg-neutral-900 border border-neutral-800 p-4 rounded-t-2xl">
        <div className="flex items-center text-sm text-neutral-400">
          <Edit3 className="w-4 h-4 mr-2" />
          Double-click any cell to manually edit before exporting.{' '}
          {rowData.length < totalRows
            ? `(Previewing ${rowData.length} of ${totalRows} rows)`
            : `(${totalRows} rows)`}
        </div>
        <button
          onClick={handleDownload}
          className="flex items-center px-4 py-2 bg-green-500 text-black text-sm font-medium rounded-lg hover:bg-green-400 transition-colors"
        >
          <Download className="w-4 h-4 mr-2" /> Download Final CSV
        </button>
      </div>

      <div className="ag-theme-alpine-dark w-full h-[500px] border-x border-b border-neutral-800 rounded-b-2xl overflow-hidden">
        <AgGridReact
          ref={gridRef}
          theme="legacy"
          rowData={rowData}
          columnDefs={columnDefs}
          defaultColDef={defaultColDef}
          pagination={true}
          paginationPageSize={100}
        />
      </div>
    </div>
  );
}

/* ─── Exports ────────────────────────────────────────────────────────────────────────────── */
