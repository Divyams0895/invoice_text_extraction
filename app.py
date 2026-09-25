# With User Interface - Streamlit

import cv2
import pytesseract
import numpy as np
import streamlit as st  
from PIL import Image
import re 

def extract_invoice_details(uploaded_image):
    """
    Extract important invoice details:
        - Invoice Number
        - Invoice Date
        - Customer Name
        - Shipping Address
        - Item
        - Quantity
        - Total / Balance Due

    Returns:
        details: dictionary containing extracted fields
        processed_image: image with customer name highlighted
    """

    # ------------------------------------------------
    # Convert PIL image -> OpenCV image
    # ------------------------------------------------
    image = np.array(uploaded_image)

    # RGB -> BGR
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


    tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    # ============================================================
    # LOAD TESSERACT
    # ============================================================

    try:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

        # Check that Tesseract can be called.
        pytesseract.get_tesseract_version()

    except Exception:
        st.error(
            "Tesseract OCR could not be initialized. "
            "Check the Tesseract executable path in the sidebar."
        )
        st.stop()

    # ------------------------------------------------
    # OCR
    # ------------------------------------------------
    data = pytesseract.image_to_data(
        image,
        output_type=pytesseract.Output.DICT
    )

    # Full OCR text
    full_text = pytesseract.image_to_string(image)

    n = len(data["text"])

    # Default values
    details = {
        "Invoice Number": None,
        "Invoice Date": None,
        "Customer Name": None,
        "Shipping Address": None,
        "Item": None,
        "Quantity": None,
        "Total": None
    }

    # =================================================
    # 1. INVOICE NUMBER
    # =================================================

    # Example:
    # # 36258

    match = re.search(
        r"#\s*(\d+)",
        full_text
    )

    if match:
        details["Invoice Number"] = match.group(1)

    # =================================================
    # 2. INVOICE DATE
    # =================================================

    # Example:
    # Date:
    # Mar 06 2012

    lines = [
        line.strip()
        for line in full_text.split("\n")
        if line.strip()
    ]

    for i, line in enumerate(lines):

        if line.lower().startswith("date"):

            if i + 1 < len(lines):
                details["Invoice Date"] = lines[i + 1]

    # =================================================
    # 3. BILL TO / CUSTOMER NAME
    # =================================================

    bill_to_index = None

    for i in range(n - 1):

        current = data["text"][i].strip().lower()
        next_text = data["text"][i + 1].strip().lower()

        if (
            current in ["bill", "bill:"]
            and next_text in ["to", "to:"]
        ):
            bill_to_index = i
            break

    customer_words = []

    if bill_to_index is not None:

        bill_x = data["left"][bill_to_index]
        bill_y = data["top"][bill_to_index]
        bill_h = data["height"][bill_to_index]

        candidates = []

        for i in range(n):

            text = data["text"][i].strip()

            if not text:
                continue

            try:
                confidence = float(data["conf"][i])
            except:
                confidence = 0

            if confidence < 50:
                continue

            x = data["left"][i]
            y = data["top"][i]

            if (
                y > bill_y + bill_h
                and y - bill_y < 100
                and abs(x - bill_x) < 250
            ):
                candidates.append(i)

        if candidates:

            customer_y = min(
                data["top"][i]
                for i in candidates
            )

            for i in candidates:

                if abs(
                    data["top"][i] - customer_y
                ) < 10:

                    customer_words.append(
                        (
                            data["left"][i],
                            data["top"][i],
                            data["width"][i],
                            data["height"][i],
                            data["text"][i].strip()
                        )
                    )

            customer_words.sort(
                key=lambda x: x[0]
            )

            details["Customer Name"] = " ".join(
                word[4]
                for word in customer_words
            )

    # =================================================
    # 4. SHIPPING ADDRESS
    # =================================================

    ship_to_index = None

    for i in range(n - 1):

        current = data["text"][i].strip().lower()
        next_text = data["text"][i + 1].strip().lower()

        if (
            current in ["ship", "ship:"]
            and next_text in ["to", "to:"]
        ):
            ship_to_index = i
            break

    if ship_to_index is not None:

        ship_x = data["left"][ship_to_index]
        ship_y = data["top"][ship_to_index]
        ship_h = data["height"][ship_to_index]

        address_lines = []

        for i in range(n):

            text = data["text"][i].strip()

            if not text:
                continue

            y = data["top"][i]
            x = data["left"][i]

            if (
                y > ship_y + ship_h
                and y - ship_y < 150
                and x > ship_x - 20
                and x < ship_x + 300
            ):

                try:
                    confidence = float(data["conf"][i])
                except:
                    confidence = 0

                if confidence >= 50:
                    address_lines.append(
                        (
                            data["top"][i],
                            data["left"][i],
                            text
                        )
                    )

        # Sort by Y, then X
        address_lines.sort(
            key=lambda x: (x[0], x[1])
        )

        # Group words into lines
        grouped_lines = {}

        for y, x, text in address_lines:

            found_line = None

            for existing_y in grouped_lines:

                if abs(existing_y - y) < 10:
                    found_line = existing_y
                    break

            if found_line is None:
                grouped_lines[y] = [(x, text)]
            else:
                grouped_lines[found_line].append(
                    (x, text)
                )

        address = []

        for y in sorted(grouped_lines):

            words = sorted(
                grouped_lines[y],
                key=lambda x: x[0]
            )

            address.append(
                " ".join(word for _, word in words)
            )

        if address:
            details["Shipping Address"] = ", ".join(
                address
            )

    # =================================================
    # 5. ITEM
    # =================================================

    item_index = None

    for i in range(n):

        text = data["text"][i].strip().lower()

        if text == "item":
            item_index = i
            break

    if item_index is not None:

        item_x = data["left"][item_index]
        item_y = data["top"][item_index]
        item_h = data["height"][item_index]

        item_words = []

        for i in range(n):

            text = data["text"][i].strip()

            if not text:
                continue

            x = data["left"][i]
            y = data["top"][i]

            # Item description is below table header
            # and on left side
            if (
                y > item_y + item_h + 10
                and y - item_y < 100
                and x < 600
            ):

                try:
                    confidence = float(data["conf"][i])
                except:
                    confidence = 0

                if confidence >= 50:
                    item_words.append(
                        (
                            x,
                            y,
                            text
                        )
                    )

        if item_words:

            # First line after table header
            first_y = min(
                word[1]
                for word in item_words
            )

            first_line = [
                word
                for word in item_words
                if abs(word[1] - first_y) < 10
            ]

            first_line.sort(
                key=lambda x: x[0]
            )

            details["Item"] = " ".join(
                word[2]
                for word in first_line
            )

    # =================================================
    # 6. QUANTITY
    # =================================================

    # In your invoice the quantity is 1.
    # Look for a number around the Quantity column.

    quantity_match = re.search(
        r"\n\s*(\d+)\s*\n",
        full_text
    )

    if quantity_match:
        details["Quantity"] = quantity_match.group(1)

    # =================================================
    # 7. TOTAL / BALANCE DUE
    # =================================================

    # Look for:
    # Balance Due: $50.10
    # OR
    # Total: $50.10

    balance_match = re.search(
        r"Balance\s+Due:\s*\$?\s*([\d,]+\.\d{2})",
        full_text,
        re.IGNORECASE
    )

    total_match = re.search(
        r"Total:\s*\$?\s*([\d,]+\.\d{2})",
        full_text,
        re.IGNORECASE
    )

    if balance_match:

        details["Total"] = "$" + balance_match.group(1)

    elif total_match:

        details["Total"] = "$" + total_match.group(1)

    # =================================================
    # Highlight customer name
    # =================================================

    if customer_words:

        x1 = min(
            word[0]
            for word in customer_words
        )

        y1 = min(
            word[1]
            for word in customer_words
        )

        x2 = max(
            word[0] + word[2]
            for word in customer_words
        )

        y2 = max(
            word[1] + word[3]
            for word in customer_words
        )

        # Green rectangle
        cv2.rectangle(
            image,
            (x1 - 5, y1 - 5),
            (x2 + 5, y2 + 5),
            (0, 255, 0),
            3
        )

        # Customer label
        cv2.putText(
            image,
            f"Customer: {details['Customer Name']}",
            (x1, max(20, y1 - 15)),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2
        )

    # BGR -> RGB
    processed_image = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2RGB
    )

    return details, processed_image 

# ============= STREAMLIT UI ======== #

st.set_page_config(
    page_title = 'Invoice Details - OCR',
    page_icon = '🧾',
    layout = 'wide'
)

st.title("OCR - Invoice Text Extraction")
st.caption("Get details from invoice using OCR")

upload_file = st.file_uploader("Upload invoice image",type=["jpg","jpeg","png"])

if upload_file is not None:

    image = Image.open(upload_file)

    col1, col2, col3 = st.columns(3)

    with col1:

        st.subheader("Original Image")
        st.image(image,caption="Invoice",width="stretch")

    details, processed_image = extract_invoice_details(image)

    # ------------------------------------------------
    # Display result
    # ------------------------------------------------
    with col2:

        if details:

            st.subheader("Processed Invoice")

            # Show image with bounding box + name
            st.image(
                processed_image,
                caption="Invoice details detected",
                width="stretch"
            )

        else:

            st.warning(
                "Invoice details could not be detected."
            )
    st.success(
        f"Invoice Details: {details}"
    )
    with col3:
        # Show extracted customer name
        st.subheader("Invoice Details")

        with st.container(border=True):
            st.write(f"**Name:** {details['Customer Name']}")
            st.write(f"**Invoice Number:** {details['Invoice Number']}")
            st.write(f"**Invoice Date:** {details['Invoice Date']}")
            st.write(f"**Shipping Address:** {details['Shipping Address']}")
            st.write(f"**Item:** {details['Item']}")
            st.write(f"**Quantity:** {details['Quantity']}")
            st.write(f"**Total Price:** :green[{details['Total']}]")






