const themeStorageKey = "ups-pi-node-theme";
const widgetStyleStorageKey = "ups-pi-node-widget-style";
const customWidgetLinkId = "custom-widget-css";
const builtinWidgetStyleOptions = [
    { id: "neon", label: "1. Neon Tech Widget", custom: false },
    { id: "glass", label: "2. Glassmorphism Dashboard", custom: false },
    { id: "oled", label: "3. Minimal OLED Widget", custom: false },
    { id: "home", label: "4. Smart Home Energy Card", custom: false },
    { id: "control", label: "5. Futuristic Control Panel", custom: false },
    { id: "mobile", label: "6. Mobile App Style Widget", custom: false },
    { id: "industrial", label: "7. Industrial Monitoring Widget", custom: false },
    { id: "liquid", label: "8. Liquid Battery Widget", custom: false },
    { id: "radial", label: "9. Radial Energy Hub", custom: false },
    { id: "premium", label: "10. Premium Dark UI", custom: false },
];
let widgetStyleOptionsCache = null;

function getWidgetStyleOptions() {
    if (widgetStyleOptionsCache) {
        return widgetStyleOptionsCache;
    }

    const optionsElement = document.getElementById("widget-style-options");
    if (!optionsElement) {
        widgetStyleOptionsCache = builtinWidgetStyleOptions;
        return widgetStyleOptionsCache;
    }

    try {
        const options = JSON.parse(optionsElement.textContent);
        widgetStyleOptionsCache = Array.isArray(options) && options.length
            ? options.filter((option) => option && option.id)
            : builtinWidgetStyleOptions;
    } catch (error) {
        widgetStyleOptionsCache = builtinWidgetStyleOptions;
    }
    return widgetStyleOptionsCache;
}

function getWidgetStyleOption(style) {
    return getWidgetStyleOptions().find((option) => option.id === style);
}

function getFallbackWidgetStyle() {
    return getWidgetStyleOption("neon") || getWidgetStyleOptions()[0] || builtinWidgetStyleOptions[0];
}

function getStoredTheme() {
    try {
        return localStorage.getItem(themeStorageKey) || "dark";
    } catch (error) {
        return "dark";
    }
}

function setTheme(theme) {
    const normalized = theme === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = normalized;
    try {
        localStorage.setItem(themeStorageKey, normalized);
    } catch (error) {
        return;
    }
}

function getStoredWidgetStyle() {
    try {
        const storedStyle = localStorage.getItem(widgetStyleStorageKey) || "neon";
        return getWidgetStyleOption(storedStyle) ? storedStyle : getFallbackWidgetStyle().id;
    } catch (error) {
        return getFallbackWidgetStyle().id;
    }
}

function applyCustomWidgetCss(styleOption) {
    let link = document.getElementById(customWidgetLinkId);
    if (styleOption && styleOption.custom && styleOption.css_url) {
        if (!link) {
            link = document.createElement("link");
            link.id = customWidgetLinkId;
            link.rel = "stylesheet";
            document.head.appendChild(link);
        }
        if (link.getAttribute("href") !== styleOption.css_url) {
            link.setAttribute("href", styleOption.css_url);
        }
        return;
    }

    if (link) {
        link.remove();
    }
}

function setWidgetStyle(style) {
    const styleOption = getWidgetStyleOption(style) || getFallbackWidgetStyle();
    const normalized = styleOption.id;
    document.documentElement.dataset.widgetStyle = normalized;
    applyCustomWidgetCss(styleOption);
    try {
        localStorage.setItem(widgetStyleStorageKey, normalized);
    } catch (error) {
        return;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const currentTheme = getStoredTheme();
    setTheme(currentTheme);
    const currentWidgetStyle = getStoredWidgetStyle();
    setWidgetStyle(currentWidgetStyle);

    const themeInputs = document.querySelectorAll("[data-theme-option]");
    for (const input of themeInputs) {
        input.checked = input.value === currentTheme;
        input.addEventListener("change", () => {
            if (input.checked) {
                setTheme(input.value);
            }
        });
    }

    const widgetStyleInputs = document.querySelectorAll("[data-widget-style-option]");
    for (const input of widgetStyleInputs) {
        input.checked = input.value === currentWidgetStyle;
        input.addEventListener("change", () => {
            if (input.checked) {
                setWidgetStyle(input.value);
            }
        });
    }

    const widgetStyleSelect = document.querySelector("[data-widget-style-select]");
    if (widgetStyleSelect) {
        widgetStyleSelect.value = currentWidgetStyle;
        if (!widgetStyleSelect.value) {
            widgetStyleSelect.value = getFallbackWidgetStyle().id;
        }
        widgetStyleSelect.addEventListener("change", () => {
            setWidgetStyle(widgetStyleSelect.value);
        });
    }
});
