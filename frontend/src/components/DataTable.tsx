import { useState, useEffect, useMemo } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import axios from 'axios';

import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

// Fixes missing module errors
ModuleRegistry.registerModules([AllCommunityModule]);

interface DataTableProps {
    sessionId: string;
    explanations?: Record<string, { feature: string; impact: number }[]>;
    isCleaned?: boolean;
}

export default function DataTable({ sessionId, explanations, isCleaned = false }: DataTableProps) {
    const [rowData, setRowData] = useState<any[]>([]);
    const [columnDefs, setColumnDefs] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            setIsLoading(true);
            try {
                const response = await axios.get(`http://127.0.0.1:8000/api/data/${sessionId}?is_cleaned=${isCleaned}`);
                const rawData = response.data.data;

                if (rawData.length > 0) {
                    const enrichedData = rawData.map((row: any, index: number) => {
                        if (row.is_anomaly && explanations && explanations[String(index)]) {
                            const reasons = explanations[String(index)]
                                .map((r: any) => `${r.feature} (${r.impact > 0 ? '+' : ''}${r.impact.toFixed(1)})`)
                                .join(" | ");
                            return { ...row, AI_Reason: reasons };
                        }
                        return { ...row, AI_Reason: "" };
                    });

                    const cols = Object.keys(enrichedData[0]).map((key) => {
                        if (key === 'AI_Reason') {
                            return {
                                field: key,
                                headerName: '🧠 AI Reason',
                                pinned: 'right',
                                width: 250,
                                hide: isCleaned,
                                cellStyle: (params: any) => {
                                    if (params.value) return { backgroundColor: 'rgba(250, 204, 21, 0.1)', color: '#facc15', fontWeight: 'bold' };
                                    return null;
                                }
                            };
                        }
                        return {
                            field: key,
                            sortable: true,
                            filter: true,
                            cellStyle: (params: any) => {
                                if (key === 'is_anomaly' && params.value === true) return { backgroundColor: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', fontWeight: 'bold' };
                                if (params.data && params.data.is_anomaly === true) return { backgroundColor: 'rgba(239, 68, 68, 0.05)' };
                                return null;
                            }
                        };
                    });

                    setColumnDefs(cols);
                    setRowData(enrichedData);
                }
            } catch (error) {
                console.error("Failed to fetch data:", error);
            } finally {
                setIsLoading(false);
            }
        };

        if (sessionId) fetchData();
    }, [sessionId, explanations, isCleaned]);

    const defaultColDef = useMemo(() => ({ flex: 1, minWidth: 150, resizable: true }), []);

    if (isLoading) return <div className="text-neutral-500 text-sm animate-pulse flex items-center justify-center h-40">Loading dataset into grid...</div>;

    return (
        <div className="ag-theme-alpine-dark w-full h-[500px] mt-6 rounded-xl overflow-hidden border border-neutral-800 transition-all duration-500">
            <AgGridReact
                theme="legacy" // Fixes the AG Grid v33 CSS collision error
                rowData={rowData}
                columnDefs={columnDefs}
                defaultColDef={defaultColDef}
                pagination={true}
                paginationPageSize={100}
                animateRows={true}
            />
        </div>
    );
}