const diseaseData = {
    dengue: [30, 25, 20, 10, 10, 5],
    ab_diarrhea: [20, 30, 15, 20, 10, 5],
    typhoid: [25, 20, 25, 15, 10, 5],
    leptospirosis: [15, 20, 30, 15, 15, 5]
};

// Remove JSON.parse() if climateImpactData is passed as an object
const climateFactors = ["tave", "tmin", "tmax", "heat_index", "pr", "wind_speed", "rh", "solar_rad", "uv_rad"];

const climateImpactData = {
    'DENGUE FEVER': { tave: 13.7, tmin: 9.3, tmax: 15.4, heat_index: 8.7, pr: 6.8, wind_speed: 12.3, rh: 21.6, solar_rad: 6.1, uv_rad: 5.7 },
    'ACUTE BLOODY DIARRHEA': { tave: 19.4, tmin: 16.7, tmax: 17.3, heat_index: 17.7, pr: 1.5, wind_speed: 9.9, rh: 13.1, solar_rad: 2.4, uv_rad: 1.6 },
    'TYPHOID FEVER': { tave: 10.8, tmin: 6.5, tmax: 12.5, heat_index: 8.4, pr: 8.3, wind_speed: 10.3, rh: 34.0, solar_rad: 4.6, uv_rad: 4.1 },
    'LEPTOSPIROSIS': { tave: 10.4, tmin: 6.2, tmax: 9.6, heat_index: 5.1, pr: 10.9, wind_speed: 4.0, rh: 26.8, solar_rad: 13.7, uv_rad: 12.8 }
};


// Default to a disease (e.g., "DENGUE FEVER") for initial pie chart rendering
const initialDisease = 'DENGUE FEVER';
const initialDiseaseData = climateImpactData[initialDisease];

// Prepare initial data for the pie chart
const initialPieData = climateFactors.map(factor => initialDiseaseData[factor]);

// Initialize pie chart with the default data
const ctx = document.getElementById('pieChart').getContext('2d');
let pieChart = new Chart(ctx, {
    type: 'pie',
    data: {
        labels: ['Average Temperature', 'Min Temperature', 'Max Temperature', 'Heat Index', 'Precipitation', 'Wind Speed', 'Humidity', 'Solar Radiation', 'UV Radiation'],
        datasets: [{
            data: initialPieData, // Default to Dengue data or any initial data
            backgroundColor: ['#023e8a', '#c1121f', '#3a5a40', '#8338ec', '#6a040f', '#240046', '#33658a', '#0d21a1', '#d90368']
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
        //labels: ['Cagayan De Oro City', 'City of Mandaluyong', 'City of Muntinlupa', 'City of Navotas', 'Dagupan City', 'Davao City', 'Iloilo City', 'Legazpi City', 'Mandaue City', 'Palayan City', 'Tacloban City', 'Zamboanga City'],
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

// pie chart dropdowns
const dropdownButton = document.getElementById('dropdownButton');
const dropdownMenu = document.getElementById('dropdownMenu');
const dropdownSelectedValue = document.getElementById('dropdownSelectedValue');

// Toggle dropdown visibility
dropdownButton.addEventListener('click', () => {
    dropdownMenu.classList.toggle('hidden');
});

// Update pie chart based on selected disease
dropdownMenu.addEventListener('click', (event) => {
    const selectedDisease = event.target.getAttribute('data-value');
    dropdownSelectedValue.innerText = event.target.innerText;
    updatePieChart(selectedDisease);
});

function updatePieChart(disease) {
    const diseaseData = climateImpactData[disease];
    const updatedPieData = climateFactors.map(factor => diseaseData[factor]);

    pieChart.data.datasets[0].data = updatedPieData;
    pieChart.update();
}

// Close the dropdown if clicked outside
document.addEventListener('click', (event) => {
    if (!dropdownButton.contains(event.target) && !dropdownMenu.contains(event.target)) {
        dropdownMenu.classList.add('hidden');
    }
});