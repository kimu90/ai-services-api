# static/js/custom.js

// Theme handling
document.addEventListener('DOMContentLoaded', function() {
    // Initialize theme
    const currentTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', currentTheme);
    
    // Theme toggle function
    window.toggleTheme = function() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        
        // Trigger Streamlit theme update
        if (window.Streamlit) {
            window.Streamlit.setComponentValue({
                theme: newTheme
            });
        }
    }
});

// Custom chart animations
function initializeChartAnimations() {
    const charts = document.querySelectorAll('.chart-container');
    
    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('fade-in');
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.1 }
    );
    
    charts.forEach(chart => observer.observe(chart));
}

// Metric animations
function animateMetrics() {
    const metrics = document.querySelectorAll('.metric-value');
    
    metrics.forEach(metric => {
        const targetValue = parseFloat(metric.getAttribute('data-value'));
        const duration = 1000; // Animation duration in milliseconds
        const startValue = 0;
        const startTime = performance.now();
        
        function updateValue(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Easing function
            const easeOutQuad = progress => 1 - (1 - progress) * (1 - progress);
            
            const currentValue = startValue + (targetValue - startValue) * easeOutQuad(progress);
            metric.textContent = currentValue.toLocaleString(undefined, {
                minimumFractionDigits: 0,
                maximumFractionDigits: 1
            });
            
            if (progress < 1) {
                requestAnimationFrame(updateValue);
            }
        }
        
        requestAnimationFrame(updateValue);
    });
}

// Table sorting and filtering
function initializeTableFunctionality() {
    const tables = document.querySelectorAll('.streamlit-table');
    
    tables.forEach(table => {
        const headers = table.querySelectorAll('th');
        
        headers.forEach(header => {
            header.addEventListener('click', () => {
                const column = header.cellIndex;
                const rows = Array.from(table.querySelectorAll('tr')).slice(1);
                const isNumeric = !isNaN(rows[0].cells[column].textContent);
                
                rows.sort((a, b) => {
                    const aValue = a.cells[column].textContent;
                    const bValue = b.cells[column].textContent;
                    
                    if (isNumeric) {
                        return parseFloat(aValue) - parseFloat(bValue);
                    }
                    return aValue.localeCompare(bValue);
                });
                
                if (header.classList.contains('sorted-asc')) {
                    rows.reverse();
                    header.classList.remove('sorted-asc');
                    header.classList.add('sorted-desc');
                } else {
                    header.classList.remove('sorted-desc');
                    header.classList.add('sorted-asc');
                }
                
                table.tBodies[0].append(...rows);
            });
        });
    });
}

// Export functionality
function initializeExport() {
    window.exportData = function(data, filename) {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
    
    window.exportCSV = function(data, filename) {
        const csv = convertToCSV(data);
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}

// Utility functions
function convertToCSV(data) {
    if (!data.length) return '';
    
    const headers = Object.keys(data[0]);
    const rows = data.map(row => 
        headers.map(header => 
            JSON.stringify(row[header] || '')
        ).join(',')
    );
    
    return [
        headers.join(','),
        ...rows
    ].join('\n');
}

// Initialize all functionality
document.addEventListener('DOMContentLoaded', function() {
    initializeChartAnimations();
    initializeTableFunctionality();
    initializeExport();
    
    // Initialize metrics after Streamlit loads
    if (window.Streamlit) {
        window.Streamlit.addEventListener('load', animateMetrics);
    }
});

// Custom event handlers
document.addEventListener('streamlit:load', function() {
    // Reinitialize components after Streamlit updates
    initializeChartAnimations();
    animateMetrics();
});

// Error handling
window.addEventListener('error', function(event) {
    console.error('JavaScript Error:', event.error);
    
    if (window.Streamlit) {
        window.Streamlit.setComponentValue({
            error: {
                message: event.error.message,
                stack: event.error.stack
            }
        });
    }
});
