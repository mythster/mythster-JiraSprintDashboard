/*
 * script.js
 *
 * Author: mythster (Ashir Gowardhan)
 * Date Created: 2025-05-19
 * Description: Handles all client-side logic for the Jira Sprint Dashboard.
 * It fetches the `data.json` file, populates the sprint and user
 * filters, and uses Chart.js to render and update the burn-up
 * and EV/PV charts based on user selections.
 *
 * Copyright 2024 mythster
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

document.addEventListener('DOMContentLoaded', () => {
    const state = {
        burnupChart: null,
        fullData: null,
    };

    const elements = {
        viewSelector: document.getElementById('viewSelector'),
        sprintControls: document.getElementById('sprintControls'),
        sprintFilter: document.getElementById('sprintFilter'),
        userFilter: document.getElementById('userFilter'),
        chartCanvas: document.getElementById('burnupChart').getContext('2d'),
        chartContainer: document.querySelector('.chart-container'),
    };

    async function initializeDashboard() {
        try {
            const response = await fetch(`data.json?v=${new Date().getTime()}`);
            if (!response.ok) throw new Error('data.json not found. Please run the Python script first.');
            state.fullData = await response.json();
            
            if (!state.fullData || Object.keys(state.fullData).length === 0) {
                throw new Error('data.json is empty or invalid. Please run the Python script to generate data.');
            }
            
            const sprintNames = Object.keys(state.fullData).filter(name => name !== "All Time" && name !== "EV/PV");
            populateSprintFilter(sprintNames);
            
            handleViewChange();

            elements.viewSelector.addEventListener('change', handleViewChange);
            elements.sprintFilter.addEventListener('change', updateSprintDashboard);
            elements.userFilter.addEventListener('change', updateSprintDashboard);

        } catch (error) {
            console.error('Error initializing dashboard:', error);
            elements.chartContainer.innerHTML = `<p style="color: #f43f5e; text-align: center;">${error.message}</p>`;
        }
    }

    function handleViewChange() {
        const selectedView = elements.viewSelector.value;
        elements.sprintControls.style.display = 'none';

        if (selectedView === 'ev_pv') {
            if (state.fullData['EV/PV']) {
                const chartTitle = "Performance: Earned Value vs. Planned Value (All Time)";
                drawEvPvChart(state.fullData['EV/PV'], chartTitle);
            }
        } else {
            elements.sprintControls.style.display = 'flex';
            updateSprintDashboard();
        }
    }

    function populateSprintFilter(sprintNames) {
        elements.sprintFilter.innerHTML = '';
        sprintNames.sort((a, b) => {
            const numA = parseInt(a.match(/\d+/)?.[0] || -1);
            const numB = parseInt(b.match(/\d+/)?.[0] || -1);
            return numA - numB;
        });

        sprintNames.forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            elements.sprintFilter.appendChild(option);
        });

        if (sprintNames.length > 0) {
            elements.sprintFilter.selectedIndex = sprintNames.length - 1;
        }
    }
  
    function updateSprintDashboard() {
        const selectedSprint = elements.sprintFilter.value;
        if (!selectedSprint || !state.fullData[selectedSprint]) {
           if(state.burnupChart) state.burnupChart.clear();
           console.error(`Data for sprint "${selectedSprint}" not found.`);
           return;
        }
        const sprintData = state.fullData[selectedSprint];
        
        populateUserFilter(sprintData.users);
        const selectedUser = elements.userFilter.value;
        const chartTitle = `Burn-Up: ${elements.sprintFilter.value} - ${elements.userFilter.options[elements.userFilter.selectedIndex].text}`;
        drawChart(sprintData, selectedUser, chartTitle, true);
    }
  
    function populateUserFilter(users = []) {
        const currentUser = elements.userFilter.value;
        elements.userFilter.innerHTML = '';
        const overallOption = document.createElement('option');
        overallOption.value = 'overall';
        overallOption.textContent = 'Overall Team';
        elements.userFilter.appendChild(overallOption);

        users.forEach(user => {
            const option = document.createElement('option');
            option.value = user;
            option.textContent = user;
            elements.userFilter.appendChild(option);
        });

        if ([...elements.userFilter.options].some(opt => opt.value === currentUser)) {
            elements.userFilter.value = currentUser;
        }
    }
  
    function drawChart(sprintData, userKey, chartTitle, showIdeal) {
        if (!sprintData?.charts?.[userKey]) {
            if(state.burnupChart) state.burnupChart.clear();
            console.error(`Chart data not found for user: ${userKey}`);
            return;
        }

        const chartData = sprintData.charts[userKey];
        const { dates } = sprintData;
        const { earnedHours, actualCost, dailyPlannedHours } = chartData;

        let plannedHoursData = dailyPlannedHours || [];
        const finalPlanned = plannedHoursData[plannedHoursData.length - 1] || 0;
        const idealBurnupData = dates.map((_, index) => (dates.length <= 1) ? 0 : (finalPlanned / (dates.length - 1)) * index);

        const maxPlanned = Math.max(0, ...plannedHoursData.filter(v => v != null));
        const maxEarned = Math.max(0, ...earnedHours.filter(v => v != null));
        let yAxisTop = Math.ceil(Math.max(maxPlanned, maxEarned) * 1.05 / 50) * 50;
        
        const datasets = [
            { label: 'Earned Hours', data: earnedHours, borderColor: '#38bdf8', backgroundColor: 'rgba(56, 189, 248, 0.2)', fill: true, tension: 0.1 },
            { label: 'Actual Cost', data: actualCost, borderColor: '#f43f5e', fill: false, tension: 0.1 },
            { label: 'Total Planned Hours', data: plannedHoursData, borderColor: '#34d399', borderDash: [5, 5], fill: false, pointRadius: 0, steppped: true }
        ];

        if (showIdeal) {
            datasets.push({ label: 'Ideal Burn-up', data: idealBurnupData, borderColor: '#facc15', borderDash: [5, 5], fill: false, pointRadius: 0 });
        }

        if (state.burnupChart) state.burnupChart.destroy();

        state.burnupChart = new Chart(elements.chartCanvas, {
            type: 'line',
            data: { labels: dates, datasets },
            options: chartOptions(chartTitle, 'Hours'),
        });
    }

    function drawEvPvChart(evPvData, chartTitle) {
        if (!evPvData?.charts?.overall) {
            if(state.burnupChart) state.burnupChart.destroy();
            console.error(`EV/PV data not found.`);
            return;
        }

        const { dates, charts } = evPvData;
        const { earnedValue, plannedValue } = charts.overall;

        if (state.burnupChart) state.burnupChart.destroy();

        state.burnupChart = new Chart(elements.chartCanvas, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [
                    { label: 'Earned Value (EV)', data: earnedValue, borderColor: '#38bdf8', backgroundColor: 'rgba(56, 189, 248, 0.2)', fill: true, tension: 0.1 },
                    { label: 'Planned Value (PV)', data: plannedValue, borderColor: '#34d399', fill: false, tension: 0.1 }
                ]
            },
            options: chartOptions(chartTitle, 'Cumulative Story Points'),
        });
    }

    function chartOptions(chartTitle, yAxisLabel) {
        return {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                title: { display: true, text: chartTitle, color: '#f9fafb', font: { size: 18, weight: '600' } },
                legend: { labels: { color: '#e5e7eb', font: {size: 14} } },
                tooltip: {
                    backgroundColor: 'rgba(20, 26, 39, 0.8)', titleColor: '#f9fafb', bodyColor: '#e5e7eb',
                    borderColor: 'rgba(255, 255, 255, 0.1)', borderWidth: 1, padding: 10, displayColors: true, boxPadding: 4,
                }
            },
            scales: {
                x: { ticks: { color: '#9ca3af' }, grid: { color: 'rgba(255, 255, 255, 0.1)' } },
                y: {
                    type: 'linear', position: 'left', min: 0,
                    title: { display: true, text: yAxisLabel, color: '#d1d5db', font: {size: 14, weight: 'bold'}},
                    ticks: { color: '#9ca3af' }, grid: { color: 'rgba(255, 255, 255, 0.1)' }
                }
            }
        };
    }

    initializeDashboard();
    
    particlesJS("particles-js", {"particles":{"number":{"value":80,"density":{"enable":true,"value_area":800}},"color":{"value":"#ffffff"},"shape":{"type":"circle","stroke":{"width":0,"color":"#000000"},"polygon":{"nb_sides":5}},"opacity":{"value":0.5,"random":false,"anim":{"enable":false,"speed":1,"opacity_min":0.1,"sync":false}},"size":{"value":3,"random":true,"anim":{"enable":false,"speed":40,"size_min":0.1,"sync":false}},"line_linked":{"enable":true,"distance":150,"color":"#ffffff","opacity":0.4,"width":1},"move":{"enable":true,"speed":2,"direction":"none","random":false,"straight":false,"out_mode":"out","bounce":false,"attract":{"enable":false,"rotateX":600,"rotateY":1200}}},"interactivity":{"detect_on":"canvas","events":{"onhover":{"enable":true,"mode":"repulse"},"onclick":{"enable":true,"mode":"push"},"resize":true},"modes":{"grab":{"distance":400,"line_linked":{"opacity":1}},"bubble":{"distance":400,"size":40,"duration":2,"opacity":8,"speed":3},"repulse":{"distance":200,"duration":0.4},"push":{"particles_nb":4},"remove":{"particles_nb":2}}},"retina_detect":true});
});
