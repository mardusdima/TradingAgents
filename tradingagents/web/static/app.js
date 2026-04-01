async function loadStatus() {
  const healthNode = document.getElementById("health-status");
  const providerNode = document.getElementById("provider-count");
  const analystNode = document.getElementById("analyst-count");

  try {
    const [healthResponse, optionsResponse] = await Promise.all([
      fetch("/health"),
      fetch("/api/options"),
    ]);

    const health = await healthResponse.json();
    const options = await optionsResponse.json();

    healthNode.textContent = health.status;
    providerNode.textContent = String((options.providers || []).length);
    analystNode.textContent = String((options.analysts || []).length);
  } catch (error) {
    healthNode.textContent = "error";
    providerNode.textContent = "-";
    analystNode.textContent = "-";
  }
}

loadStatus();
