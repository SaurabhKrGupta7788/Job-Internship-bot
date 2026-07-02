import logging
from typing import List, Dict, Any, Optional
import os

logger = logging.getLogger("PlaywrightFormDOM")

class LayoutElement:
    """Represents a simplified form field element extracted from the page layout."""
    def __init__(self, selector: str, element_type: str, label: str, value: str = "", options: Optional[List[str]] = None):
        self.selector = selector
        self.element_type = element_type
        self.label = label
        self.value = value
        self.options = options or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selector": self.selector,
            "type": self.element_type,
            "label": self.label,
            "value": self.value,
            "options": self.options
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LayoutElement':
        return cls(
            selector=data.get("selector", ""),
            element_type=data.get("type", "text"),
            label=data.get("label", ""),
            value=data.get("value", ""),
            options=data.get("options", [])
        )

class LayoutData:
    """Wraps the list of layout elements extracted from the page."""
    def __init__(self, elements: List[LayoutElement], raw_html: str = ""):
        self.elements = elements
        self.raw_html = raw_html

class PlaywrightFormDOM:
    """Extracts form fields and fills them natively using Playwright."""
    
    def __init__(self, page):
        self.page = page

    def get_page_layout(self) -> LayoutData:
        """
        Retrieves the simplified page structure from the active browser tab,
        piercing through all iframes to find inputs.
        """
        layout_elements = []
        
        # Helper to extract from a specific frame
        def extract_from_frame(frame):
            elements = frame.evaluate('''() => {
                const inputs = Array.from(document.querySelectorAll('input, select, textarea'));
                return inputs.map(el => {
                    let label = "";
                    if (el.id) {
                        const lbl = document.querySelector(`label[for="${el.id}"]`);
                        if (lbl) label = lbl.innerText;
                    }
                    if (!label && el.name) label = el.name;
                    if (!label && el.placeholder) label = el.placeholder;
                    if (!label && el.ariaLabel) label = el.ariaLabel;
                    
                    let selector = el.id ? `#${el.id}` : (el.name ? `[name="${el.name}"]` : null);
                    if (!selector) return null;
                    
                    let options = [];
                    if (el.tagName.toLowerCase() === 'select') {
                        options = Array.from(el.options).map(o => o.text.trim());
                    }
                    
                    return {
                        selector: selector,
                        type: el.tagName.toLowerCase() === 'select' ? 'select' : el.type,
                        label: label.trim(),
                        value: el.value || "",
                        options: options
                    };
                }).filter(Boolean);
            }''')
            return [LayoutElement.from_dict(e) for e in elements]
            
        all_frames = [self.page] + self.page.frames
        for frame in all_frames:
            try:
                frame_elements = extract_from_frame(frame)
                layout_elements.extend(frame_elements)
            except Exception as e:
                logger.debug(f"Failed to extract from iframe: {e}")
                
        return LayoutData(elements=layout_elements, raw_html="")

    def _find_locator_in_frames(self, selector: str):
        """Finds a locator for the selector across all frames."""
        all_frames = [self.page] + self.page.frames
        for frame in all_frames:
            try:
                el = frame.locator(selector).first
                # Use a small timeout just to check visibility
                if el.is_visible(timeout=500):
                    return el
            except:
                continue
        return None

    def fill_field(self, selector: str, value: str) -> bool:
        """
        Fills a text, email, number or select field with the specified value, piercing iframes.
        """
        try:
            elem = self._find_locator_in_frames(selector)
            if not elem:
                logger.error(f"Failed to find element {selector} for filling.")
                return False
                
            tag_name = elem.evaluate("el => el.tagName.toLowerCase()")
            if tag_name == "select":
                elem.select_option(label=value, force=True)
            else:
                elem.fill(value, force=True)
            return True
        except Exception as e:
            logger.error(f"Failed to fill {selector}: {e}")
            return False

    def upload_file(self, selector: str, filepath: str) -> bool:
        """
        Uploads a local file to the specified file input element, piercing iframes.
        """
        try:
            elem = self._find_locator_in_frames(selector)
            if not elem:
                logger.error(f"Failed to find element {selector} for file upload.")
                return False
                
            elem.set_input_files(os.path.abspath(filepath))
            return True
        except Exception as e:
            logger.error(f"Failed to upload file {filepath} to {selector}: {e}")
            return False
