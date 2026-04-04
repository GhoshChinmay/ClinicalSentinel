import { useState, useEffect, useRef, useMemo } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import axios from 'axios';
import { Download, Edit3 } from 'lucide-react';

// ADDED: The missing CSS files that make it look like Excel!
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

ModuleRegistry.registerModules([AllCommunityModule]);

export default function ReviewEdit({ sessionId }: { sessionId: string }) {
    const [rowData, setRowData] = useState<any[]>([]);
    const [columnDefs, setColumnDefs] = useState<any[]>([]);
    const gridRef = useRef<AgGridReact>(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await axios.get(`http://127.0.0.1:8000/api/data/${sessionId}?is_cleaned=true`);
                const data = res.data.data;
                if (data.length > 0) {
                    setColumnDefs(Object.keys(data[0]).map(key => ({ field: key, sortable: true, filter: true })));
                    setRowData(data);
                }
            } catch (err) {
                console.error("Failed to load clean data");
            }
        };
        if (sessionId) fetchData();
    }, [sessionId]);

    const defaultColDef = useMemo(() => ({ flex: 1, minWidth: 120, resizable: true, editable: true }), []);

    const handleDownload = () => {
        gridRef.current?.api.exportDataAsCsv({ fileName: 'DataSentinel_Cleaned.csv' });
    };

    return (
        <div className="w-full mt-6">
            <div className="flex justify-between items-center bg-neutral-900 border border-neutral-800 p-4 rounded-t-2xl">
                <div className="flex items-center text-sm text-neutral-400">
                    <Edit3 className="w-4 h-4 mr-2" /> Double-click any cell to manually edit before exporting.
                </div>
                <button onClick={handleDownload} className="flex items-center px-4 py-2 bg-green-500 text-black text-sm font-medium rounded-lg hover:bg-green-400 transition-colors">
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