// 30-day entries vs. exits chart (Chart.js 4).
// Colors come from a palette validated for color blindness and contrast; identity never
// depends on color alone: there is a legend, direct labels at the line ends and a data table.
(() => {
  const canvas = document.getElementById("flowChart");
  const dataTag = document.getElementById("flow-data");
  if (!canvas || !dataTag) return;

  if (typeof Chart === "undefined") {
    // The CDN could not be reached: the table below still has every number.
    canvas.parentElement.innerHTML =
      '<p class="text-body-secondary small mb-0">No se pudo cargar el gráfico. Abre "Ver los datos como tabla".</p>';
    return;
  }

  const data = JSON.parse(dataTag.textContent);
  const COLORS = { in: "#2a78d6", out: "#eb6834" };
  const money = new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" });
  const integer = new Intl.NumberFormat("es-PE", { maximumFractionDigits: 0 });

  const METRICS = {
    value: { in: data.in_value, out: data.out_value, format: (v) => money.format(v) },
    count: { in: data.in_count, out: data.out_count, format: (v) => integer.format(v) },
  };
  let metric = METRICS.value;

  const isEmpty = () => [...metric.in, ...metric.out].every((v) => v === 0);

  // Vertical guide line at the hovered day (crosshair).
  const crosshair = {
    id: "crosshair",
    afterDatasetsDraw(chart) {
      const active = chart.tooltip?.getActiveElements();
      if (!active?.length) return;
      const { ctx, chartArea } = chart;
      const x = active[0].element.x;
      ctx.save();
      ctx.strokeStyle = "rgba(0, 0, 0, 0.25)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, chartArea.top);
      ctx.lineTo(x, chartArea.bottom);
      ctx.stroke();
      ctx.restore();
    },
  };

  // Series name next to the last point of each line, in text color (not the series color).
  const directLabels = {
    id: "directLabels",
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      ctx.save();
      ctx.font = "12px system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
      ctx.fillStyle = "#495057";
      ctx.textBaseline = "middle";
      const placed = [];
      chart.data.datasets.forEach((dataset, i) => {
        const meta = chart.getDatasetMeta(i);
        if (meta.hidden || !meta.data.length) return;
        const last = meta.data[meta.data.length - 1];
        let y = last.y;
        // Nudge apart when both lines end at the same height.
        placed.forEach((other) => { if (Math.abs(other - y) < 14) y = other + (y >= other ? 14 : -14); });
        placed.push(y);
        ctx.fillText(dataset.label, last.x + 8, y);
      });
      ctx.restore();
    },
  };

  // Message over an empty plot, instead of a flat line that looks like an error.
  const emptyState = {
    id: "emptyState",
    afterDraw(chart) {
      if (!isEmpty()) return;
      const { ctx, chartArea } = chart;
      ctx.save();
      ctx.font = "14px system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
      ctx.fillStyle = "#6c757d";
      ctx.textAlign = "center";
      ctx.fillText("Sin movimientos en los últimos 30 días",
        (chartArea.left + chartArea.right) / 2, (chartArea.top + chartArea.bottom) / 2);
      ctx.restore();
    },
  };

  const dataset = (label, values, color) => ({
    label,
    data: values,
    borderColor: color,
    backgroundColor: color,
    borderWidth: 2,
    tension: 0.25,
    pointRadius: 0,           // no dot on every day: thin, calm lines
    pointHoverRadius: 4,      // 8px marker on hover
    pointHoverBorderWidth: 2,
    pointHoverBorderColor: "#ffffff",
  });

  const chart = new Chart(canvas, {
    type: "line",
    data: {
      labels: data.labels,
      datasets: [dataset("Entradas", metric.in, COLORS.in), dataset("Salidas", metric.out, COLORS.out)],
    },
    plugins: [crosshair, directLabels, emptyState],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { right: 64 } }, // room for the direct labels
      interaction: { mode: "index", intersect: false }, // hover anywhere on a day
      plugins: {
        legend: {
          position: "top",
          align: "end",
          labels: { usePointStyle: true, pointStyle: "line", boxWidth: 24, color: "#495057" },
        },
        tooltip: {
          backgroundColor: "#ffffff",
          titleColor: "#212529",
          bodyColor: "#212529",
          borderColor: "#dee2e6",
          borderWidth: 1,
          padding: 10,
          usePointStyle: true,
          callbacks: {
            title: (items) => `Día ${items[0].label}`,
            label: (item) => ` ${item.dataset.label}: ${metric.format(item.parsed.y)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: "#6c757d", maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
        },
        y: {
          beginAtZero: true,
          grid: { color: "rgba(0, 0, 0, 0.06)" },
          border: { display: false },
          ticks: { color: "#6c757d", precision: 0, maxTicksLimit: 6, callback: (v) => metric.format(v) },
        },
      },
    },
  });

  // Same single axis, different measure: switching replaces the data instead of adding a 2nd axis.
  document.querySelectorAll('input[name="flow-metric"]').forEach((input) => {
    input.addEventListener("change", () => {
      metric = METRICS[input.value];
      chart.data.datasets[0].data = metric.in;
      chart.data.datasets[1].data = metric.out;
      canvas.setAttribute("aria-label", input.value === "value"
        ? "Gráfico de líneas con el valor diario de entradas y salidas de los últimos 30 días."
        : "Gráfico de líneas con el número diario de entradas y salidas de los últimos 30 días.");
      chart.update();
    });
  });
})();
