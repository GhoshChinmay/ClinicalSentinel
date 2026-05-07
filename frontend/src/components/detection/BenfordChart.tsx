import React, { useMemo } from 'react';
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import { Activity } from 'lucide-react';

interface BenfordChartProps {
  data: any[];
}

export default function BenfordChart({ data }: BenfordChartProps) {
  const chartData = useMemo(() => {
    // 1. Calculate actual leading digit frequencies
    const digitCounts: Record<string, number> = {
      '1': 0, '2': 0, '3': 0, '4': 0, '5': 0, '6': 0, '7': 0, '8': 0, '9': 0
    };
    let totalCount = 0;

    data.forEach(row => {
      Object.entries(row).forEach(([key, val]) => {
        // Skip AI-engineered/internal columns
        const lowerKey = key.toLowerCase();
        if (
          lowerKey === 'is_anomaly' ||
          lowerKey === 'ai_reason' ||
          lowerKey === 'threat_score' ||
          lowerKey === 'shap_payload' ||
          lowerKey === 'counterfactual_payload' ||
          lowerKey === 'lof_score' ||
          lowerKey === 'lstm_anomaly_score' ||
          lowerKey === 'ecod_score' ||
          lowerKey.includes('id') // skip patient/investigator IDs
        ) {
          return;
        }

        if (typeof val === 'number') {
          // Extract leading digit
          const strVal = Math.abs(val).toString().replace('.', '');
          const firstDigit = strVal.charAt(0);
          if (firstDigit >= '1' && firstDigit <= '9') {
            digitCounts[firstDigit]++;
            totalCount++;
          }
        }
      });
    });

    // 2. Format for Recharts and compare with expected Benford's Law
    const expectedBenford = [30.1, 17.6, 12.5, 9.7, 7.9, 6.7, 5.8, 5.1, 4.6];
    
    return [1, 2, 3, 4, 5, 6, 7, 8, 9].map((digit, index) => {
      const actualPct = totalCount > 0 ? (digitCounts[digit.toString()] / totalCount) * 100 : 0;
      return {
        digit: digit.toString(),
        Actual: parseFloat(actualPct.toFixed(1)),
        Expected: expectedBenford[index],
      };
    });
  }, [data]);

  return (
    <div className="bg-[#0A0A0A] border border-neutral-800 p-6 rounded-2xl mb-6 shadow-xl">
      <div className="flex items-center mb-6">
        <div className="bg-blue-500/20 p-2 rounded-lg mr-3">
          <Activity className="w-5 h-5 text-blue-400" />
        </div>
        <div>
          <h3 className="text-lg font-bold text-white">Statistical Plausibility (Benford&apos;s Law)</h3>
          <p className="text-xs text-neutral-400">
            Comparing the dataset&apos;s leading digit distribution against the expected logarithmic curve. Deviations may indicate manufactured data.
          </p>
        </div>
      </div>
      
      <div className="h-[300px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#262626" vertical={false} />
            <XAxis 
              dataKey="digit" 
              stroke="#525252" 
              tick={{ fill: '#737373', fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis 
              stroke="#525252" 
              tick={{ fill: '#737373', fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(val) => `${val}%`}
            />
            <Tooltip 
              contentStyle={{ backgroundColor: '#0A0A0A', border: '1px solid #262626', borderRadius: '8px' }}
              itemStyle={{ fontSize: '13px' }}
              labelStyle={{ color: '#A3A3A3', marginBottom: '4px' }}
              formatter={(value: any) => [`${value}%`]}
            />
            <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
            <Bar dataKey="Actual" fill="#3B82F6" radius={[4, 4, 0, 0]} maxBarSize={50} />
            <Line 
              type="monotone" 
              dataKey="Expected" 
              stroke="#F87171" 
              strokeWidth={3}
              dot={{ r: 4, fill: '#F87171', strokeWidth: 0 }}
              activeDot={{ r: 6 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
