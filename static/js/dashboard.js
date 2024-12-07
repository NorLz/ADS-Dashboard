const diseaseData = {
    dengue: [30, 25, 20, 10, 10, 5],
    ab_diarrhea: [20, 30, 15, 20, 10, 5],
    typhoid: [25, 20, 25, 15, 10, 5],
    leptospirosis: [15, 20, 30, 15, 15, 5]
};

const ctx = document.getElementById('pieChart').getContext('2d');
let pieChart = new Chart(ctx, {
    type: 'pie',
    data: {
        labels: ['UV Radiation', 'Solar Radiation', 'Temperature', 'Humidity', 'Wind Speed', 'Precipitation'],
        datasets: [{
            data: diseaseData.dengue, // Default to Dengue data
            backgroundColor: [
                '#C85890', // UV Radiation
                '#C88509', // Solar Radiation
                '#C83D09', // Temperature
                '#0998C8', // Humidity
                '#09A4A6', // Wind Speed
                '#1C497C'  // Precipitation
            ]
        }]
    },
    options: {
        responsive: false,
        plugins: {
            legend: {
                display: false // Disable the default legend
            },
            tooltip: {
                enabled: false // Disable hover tooltips
            }
        }
    },
    plugins: [{
        id: 'dataLabels',
        afterDatasetsDraw: (chart) => {
            const { ctx, data } = chart;
            const dataset = data.datasets[0];
            const total = dataset.data.reduce((sum, value) => sum + value, 0);

            chart.getDatasetMeta(0).data.forEach((dataPoint, index) => {
                const { x, y } = dataPoint.tooltipPosition();
                const value = dataset.data[index];
                const percentage = ((value / total) * 100).toFixed(0) + '%';

                ctx.fillStyle = '#fff';
                ctx.font = '14px Satoshi';
                ctx.textAlign = 'center';
                ctx.fillText(percentage, x, y + 4); // Adjust y-offset for positioning
            });
        }
    }]
});

let width, height, gradient;

function getGradient(ctx, chartArea, colors) {
    const chartWidth = chartArea.right - chartArea.left;
    const chartHeight = chartArea.bottom - chartArea.top;

    // Create a unique gradient for each bar
    const gradient = ctx.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);

    // Add color stops with specified colors and opacities
    gradient.addColorStop(0, `rgba(${colors[0]}, 0.1)`); // 80% opacity
    // gradient.addColorStop(0.5, `rgba(${colors[1]}, 0.6)`); // 60% opacity
    gradient.addColorStop(0.7, `rgba(${colors[2]}, 0.7)`); // 40% opacity

    return gradient;
}

// Define colors for each bar as RGB values
const barColors = [
    ['189, 189, 189', '','255, 102, 102'], // Gradient for the first bar
    ['189, 189, 189', '','102, 178, 102'], // Gradient for the second bar
    ['189, 189, 189','' ,'102, 102, 255'], // Gradient for the third bar
    ['189, 189, 189','','255, 193, 7'], // Gradient for the fourth bar
];

const barCtx = document.getElementById('barChart').getContext('2d');
const barChart = new Chart(barCtx, {
    type: 'bar',
    data: {
        labels: ['Dengue', 'AB Diarrhea', 'Typhoid Fever', 'Leptospirosis'],
        datasets: [{
            label: 'Cases',
            data: [32, 30, 21, 16], // Example data
            backgroundColor: function (context) {
                const { chart, dataIndex } = context;
                const { ctx, chartArea } = chart;

                if (!chartArea) {
                    return; // Wait until chartArea is available
                }

                // Pass specific colors for the gradient based on index
                return getGradient(ctx, chartArea, barColors[dataIndex]);
            },
            borderWidth: 1,
            borderRadius: 15,
            borderSkipped: false,
        }]
    },
    options: {
        responsive: false,
        plugins: {
            legend: {
                display: false
            },
            tooltip: {
                enabled: false
            }
        },
        scales: {
            x: {
                ticks: {
                    color: '#F2F2F2', // Font color for X-axis labels
                },
                grid: {
                    display: false // Disable grid lines for X-axis
                }
            },
            y: {
                ticks: {
                    display: false, // Hide numerical values on Y-axis
                },
                grid: {
                    display: false // Disable grid lines for Y-axis
                }
            }
        }
        
    },
    
    plugins: [{
        id: 'valueOnTop',
        afterDatasetsDraw: (chart) => {
            const { ctx } = chart;
            chart.data.datasets.forEach((dataset, i) => {
                const meta = chart.getDatasetMeta(i);
                meta.data.forEach((bar, index) => {
                    const value = dataset.data[index];
                    const { x, y } = bar.tooltipPosition();

                    ctx.fillStyle = '#f2f2f2'; // Text color
                    ctx.font = 'bold 12px Montserrat'; // Font style
                    ctx.textAlign = 'center';
                    ctx.fillText(value, x, y - 10); // Positioning the text above the bar
                });
            });
        }
    }]
});


// Dropdown logic
const dropdownButton = document.getElementById('dropdownButton');
const dropdownMenu = document.getElementById('dropdownMenu');
const dropdownSelectedValue = document.getElementById('dropdownSelectedValue');

// Toggle dropdown visibility
dropdownButton.addEventListener('click', () => {
    dropdownMenu.classList.toggle('hidden');
});

// Handle option selection
dropdownMenu.addEventListener('click', (event) => {
    if (event.target.dataset.value) {
        const selectedDisease = event.target.dataset.value;
        const selectedText = event.target.textContent;

        // Update the pie chart
        pieChart.data.datasets[0].data = diseaseData[selectedDisease];
        pieChart.update();

        // Update the displayed value in the dropdown button
        dropdownSelectedValue.textContent = selectedText;

        // Hide menu after selection
        dropdownMenu.classList.add('hidden');
    }
});

// Close the dropdown if clicked outside
document.addEventListener('click', (event) => {
    if (!dropdownButton.contains(event.target) && !dropdownMenu.contains(event.target)) {
        dropdownMenu.classList.add('hidden');
    }
});
