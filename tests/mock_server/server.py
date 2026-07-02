import os
from flask import Flask, render_template, request, jsonify, redirect, url_for

app = Flask(__name__, template_folder='templates')

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/linkedin/jobs/view/<int:job_id>')
def linkedin_job(job_id):
    return render_template('linkedin.html', job_id=job_id)

@app.route('/linkedin/submit', methods=['POST'])
def linkedin_submit():
    return jsonify({"status": "success", "message": "Application received"}), 200

@app.route('/linkedin/feed')
def linkedin_feed():
    return '<html><body><div class="global-nav">LinkedIn Feed</div></body></html>'

@app.route('/jobs/search/', methods=['GET'])
@app.route('/jobs/search', methods=['GET'])
def jobs_search():
    return render_template('linkedin.html', job_id=12345)

@app.route('/form_mapping_boundary')
def form_mapping_boundary():
    return """
    <html>
      <body>
        <form>
          <!-- Unicode experience question -->
          <div class="jobs-easy-apply-form-section__grouping">
            <label>Years of expëriêncê 🚀</label>
            <input type="text" id="exp_input">
          </div>
          <!-- Location question -->
          <div class="jobs-easy-apply-form-section__grouping">
            <label>Current Location / City</label>
            <input type="text" id="loc_input">
          </div>
          <!-- Notice period question -->
          <div class="jobs-easy-apply-form-section__grouping">
            <label>What is your notice period?</label>
            <input type="text" id="notice_input">
          </div>
          <!-- Select question -->
          <div class="jobs-easy-apply-form-section__grouping">
            <label>Sponsorship required?</label>
            <select id="spon_select">
              <option value="">Select option</option>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          </div>
          <!-- Empty / missing question grouping -->
          <div class="jobs-easy-apply-form-section__grouping">
            <input type="text" id="empty_input">
          </div>
          <!-- Question outside class grouping (falls back to default/except) -->
          <div>
            <label>Some other random question</label>
            <input type="text" id="other_input">
          </div>
        </form>
      </body>
    </html>
    """

@app.route('/api/layout', methods=['POST'])
def api_layout():
    return jsonify({
        "success": True,
        "layout": {
            "elements": [
                {"selector": "#first_name", "type": "text", "label": "First Name", "value": "", "options": []}
            ],
            "raw_html": "<div></div>"
        }
    }), 200

@app.route('/api/fill', methods=['POST'])
def api_fill():
    data = request.get_json() or {}
    selector = data.get("selector")
    if selector == "#invalid":
        return jsonify({"success": False, "error": "Invalid selector"}), 400
    return jsonify({"success": True}), 200

@app.route('/api/upload', methods=['POST'])
def api_upload():
    data = request.get_json() or {}
    selector = data.get("selector")
    filepath = data.get("filepath")
    
    if not selector:
        return jsonify({"success": False, "error": "Invalid selector"}), 400
    if not filepath or "nonexistent" in filepath:
        return jsonify({"success": False, "error": "File not found"}), 400
        
    if filepath and os.path.exists(filepath) and os.path.getsize(filepath) == 0:
        return jsonify({"success": False, "error": "Zero-byte file"}), 400
        
    return jsonify({"success": True}), 200

@app.route('/workday/apply/<int:step>', methods=['GET', 'POST'])
def workday_apply(step):
    if request.method == 'POST':
        next_step = step + 1
        if next_step > 3:
            return redirect(url_for('workday_submit'))
        return redirect(url_for('workday_apply', step=next_step))
    return render_template('workday.html', step=step)

@app.route('/workday/submit', methods=['GET', 'POST'])
def workday_submit():
    return jsonify({"status": "success", "message": "Workday application submitted"}), 200

@app.route('/greenhouse/apply')
def greenhouse_apply():
    return render_template('greenhouse.html')

@app.route('/greenhouse/submit', methods=['POST'])
def greenhouse_submit():
    return jsonify({"status": "success", "message": "Greenhouse application received"}), 200

if __name__ == '__main__':
    app.run(port=5001)
