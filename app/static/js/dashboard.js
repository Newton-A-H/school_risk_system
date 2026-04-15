document.addEventListener('DOMContentLoaded', function () {
  const dataElement = document.getElementById('dashboard-data');
  if (!dataElement) return;

  let dashboardData = {};
  try {
    dashboardData = JSON.parse(dataElement.textContent);
  } catch (error) {
    console.error('Failed to parse dashboard data:', error);
    return;
  }

  // Custom plugin to draw values above bars
  const valueLabelPlugin = {
    id: 'valueLabelPlugin',
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      const dataset = chart.data.datasets[0];
      const meta = chart.getDatasetMeta(0);

      ctx.save();
      ctx.font = '600 13px Inter, sans-serif';
      ctx.fillStyle = '#1e293b';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';

      meta.data.forEach((bar, index) => {
        const value = dataset.data[index];
        ctx.fillText(value, bar.x, bar.y - 8);
      });

      ctx.restore();
    }
  };

    const riskCanvas = document.getElementById('riskChart');
  if (riskCanvas) {
    const riskCounts = dashboardData.riskCounts || {};

    const labels = ['High Risk', 'Medium Risk', 'Low Risk'];
    const values = [
      Number(riskCounts['High Risk'] || 0),
      Number(riskCounts['Medium Risk'] || 0),
      Number(riskCounts['Low Risk'] || 0)
    ];

    const total = values.reduce((a, b) => a + b, 0);
    const percentages = values.map(v => total > 0 ? ((v / total) * 100).toFixed(1) : '0.0');

    const horizontalValueLabelPlugin = {
      id: 'horizontalValueLabelPlugin',
      afterDatasetsDraw(chart) {
        const { ctx } = chart;
        const dataset = chart.data.datasets[0];
        const meta = chart.getDatasetMeta(0);

        ctx.save();
        ctx.font = '600 13px Inter, sans-serif';
        ctx.fillStyle = '#0f172a';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';

        meta.data.forEach((bar, index) => {
          const value = dataset.data[index];
          const pct = percentages[index];
          ctx.fillText(`${value} learner(s) • ${pct}%`, bar.x + 12, bar.y);
        });

        ctx.restore();
      }
    };

    new Chart(riskCanvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Learners',
            data: values,
            borderRadius: 16,
            borderSkipped: false,
            backgroundColor: [
              '#ef4444', // High Risk
              '#f59e0b', // Medium Risk
              '#22c55e'  // Low Risk
            ],
            hoverBackgroundColor: [
              '#dc2626',
              '#d97706',
              '#16a34a'
            ],
            maxBarThickness: 42
          }
        ]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 1200,
          easing: 'easeOutQuart'
        },
        layout: {
          padding: {
            right: 100
          }
        },
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            backgroundColor: '#0f172a',
            titleColor: '#ffffff',
            bodyColor: '#e2e8f0',
            padding: 12,
            cornerRadius: 10,
            callbacks: {
              label: function (context) {
                const index = context.dataIndex;
                return `${context.raw} learner(s) • ${percentages[index]}%`;
              }
            }
          }
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: {
              precision: 0,
              color: '#64748b',
              font: {
                size: 12
              }
            },
            grid: {
              color: 'rgba(148, 163, 184, 0.18)',
              drawBorder: false
            }
          },
          y: {
            grid: {
              display: false
            },
            ticks: {
              color: '#334155',
              font: {
                size: 13,
                weight: '600'
              }
            }
          }
        }
      },
      plugins: [horizontalValueLabelPlugin]
    });
  }

  const importanceCanvas = document.getElementById('importanceChart');
  if (importanceCanvas) {
    const featureImportance = dashboardData.featureImportance || {};
    const entries = Object.entries(featureImportance);

    new Chart(importanceCanvas, {
      type: 'radar',
      data: {
        labels: entries.map(function (item) {
          return item[0].replaceAll('_', ' ');
        }),
        datasets: [
          {
            label: 'Importance',
            data: entries.map(function (item) {
              return Number(item[1]);
            }),
            fill: true,
            backgroundColor: 'rgba(37, 99, 235, 0.18)',
            borderColor: '#2563eb',
            borderWidth: 2,
            pointBackgroundColor: '#1d4ed8',
            pointBorderColor: '#ffffff',
            pointHoverBackgroundColor: '#ffffff',
            pointHoverBorderColor: '#1d4ed8',
            pointRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 1200,
          easing: 'easeOutQuart'
        },
        plugins: {
          legend: {
            labels: {
              color: '#334155',
              font: {
                size: 13,
                weight: '600'
              }
            }
          },
          tooltip: {
            backgroundColor: '#0f172a',
            titleColor: '#ffffff',
            bodyColor: '#e2e8f0',
            padding: 12,
            cornerRadius: 10
          }
        },
        scales: {
          r: {
            beginAtZero: true,
            angleLines: {
              color: 'rgba(148, 163, 184, 0.2)'
            },
            grid: {
              color: 'rgba(148, 163, 184, 0.2)'
            },
            pointLabels: {
              color: '#475569',
              font: {
                size: 12,
                weight: '500'
              }
            },
            ticks: {
              backdropColor: 'transparent',
              color: '#64748b'
            }
          }
        }
      }
    });
  }
});