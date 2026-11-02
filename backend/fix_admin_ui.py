"""Replace the AI tab in admin-dashboard.tsx with the new simplified design."""
import re

path = r'D:\ai_study\frontend\src\components\admin-dashboard.tsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the AI tab block
start_marker = '{tab === "ai" && ('
end_marker = '              )}\n\n              {/* TAB 5: AGENT SKILLS'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print(f'start={start_idx}, end={end_idx}')
    # Debug: find what's around line 1020
    lines = content.split('\n')
    for i in range(1018, min(1025, len(lines))):
        print(f'{i+1}: {lines[i][:80]}')
    raise SystemExit(1)

new_tab = '''{tab === "ai" && (
                <div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: 16,
                    }}
                  >
                    <div>
                      <h2 style={{ margin: 0 }}>توجيه النماذج والـ API (AI Router)</h2>
                      <p className="privacy-note" style={{ margin: "4px 0 0" }}>
                        لكل مهمة داخل المنصة يمكنك تعيين نموذج مختلف ومفتاح API مخصص.
                      </p>
                    </div>
                    <button
                      className="session-start"
                      style={{ margin: 0 }}
                      onClick={() => void startAddConfig()}
                      disabled={!!editingConfig || !!isAdding}
                    >
                      + إضافة جديد
                    </button>
                  </div>

                  {/* Add New Form */}
                  {isAdding && (
                    <section className="upload-panel" style={{ border: "2px solid var(--green)", marginBottom: 24 }}>
                      <h3 style={{ margin: "0 0 10px" }}>إضافة إعداد نموذج جديد</h3>
                      <form onSubmit={handleSaveNewConfig} style={{ display: "grid", gap: 12 }}>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                          <div>
                            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>نوع المهمة (Task Type):</label>
                            <select
                              value={taskTypeInput}
                              onChange={(e) => setTaskTypeInput(e.target.value)}
                              style={{
                                width: "100%",
                                padding: "10px",
                                border: "1px solid var(--line)",
                                borderRadius: 6,
                              }}
                            >
                              <option value="chat_qa">chat_qa — أسئلة ومساعدة المذاكرة</option>
                              <option value="quiz_generation">quiz_generation — توليد اختبارات</option>
                              <option value="flashcards">flashcards — بطاقات استذكار</option>
                              <option value="concept_map">concept_map — خرائط مفاهيم</option>
                              <option value="study_notes">study_notes — مذكرات دراسية</option>
                              <option value="audio_transcription">audio_transcription — تفريغ صوتي</option>
                              <option value="image_generation">image_generation — توليد صور</option>
                              <option value="document_ai">document_ai — تحليل مستندات</option>
                              <option value="default">default — النموذج الافتراضي</option>
                            </select>
                          </div>
                          <div>
                            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>اسم النموذج (Model):</label>
                            <input
                              required
                              value={modelInput}
                              onChange={(e) => setModelInput(e.target.value)}
                              placeholder="مثال: gemini-3.5-flash"
                              style={{
                                width: "100%",
                                padding: "10px",
                                border: "1px solid var(--line)",
                                borderRadius: 6,
                              }}
                            />
                          </div>
                        </div>

                        <div>
                          <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>
                            مفتاح Gemini API خاص (اختياري - اتركه فارغاً للاعتماد على المفتاح العام):
                          </label>
                          <input
                            type="password"
                            value={apiKeyInput}
                            onChange={(e) => setApiKeyInput(e.target.value)}
                            placeholder="المفتاح العام للمنصة"
                            style={{
                              width: "100%",
                              padding: "10px",
                              border: "1px solid var(--line)",
                              borderRadius: 6,
                            }}
                          />
                        </div>

                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                          <div>
                            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>درجة الحرارة:</label>
                            <input
                              type="number"
                              step="0.05"
                              min="0"
                              max="1"
                              value={tempInput}
                              onChange={(e) => setTempInput(Number(e.target.value))}
                              style={{ width: "100%", padding: "10px", border: "1px solid var(--line)", borderRadius: 6 }}
                            />
                          </div>
                          <div>
                            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>الحد الأقصى للتوكنز:</label>
                            <input
                              type="number"
                              min="100"
                              max="16000"
                              value={tokensInput}
                              onChange={(e) => setTokensInput(Number(e.target.value))}
                              style={{ width: "100%", padding: "10px", border: "1px solid var(--line)", borderRadius: 6 }}
                            />
                          </div>
                          <div>
                            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>نموذج Fallback (اختياري):</label>
                            <input
                              value={fallbackModelInput}
                              onChange={(e) => setFallbackModelInput(e.target.value)}
                              placeholder="مثال: gemini-3.5-flash-lite"
                              style={{ width: "100%", padding: "10px", border: "1px solid var(--line)", borderRadius: 6 }}
                            />
                          </div>
                        </div>

                        {testResult && (
                          <p style={{
                            padding: "8px 12px",
                            borderRadius: 6,
                            background: testResult.startsWith("✅") ? "#e7f0e5" : "#fff0ed",
                            fontSize: 13,
                            margin: 0,
                          }}>
                            {testResult}
                          </p>
                        )}

                        <div style={{ display: "flex", gap: 10 }}>
                          <button className="session-start" type="submit" disabled={busy || !taskTypeInput || !modelInput}>
                            {busy ? "جارٍ الحفظ…" : "حفظ وإضافة"}
                          </button>
                          <button
                            type="button"
                            className="session-start"
                            style={{ margin: 0 }}
                            onClick={() => void handleTestModel()}
                            disabled={busy || !modelInput.trim()}
                          >
                            اختبار اتصال النموذج الآن
                          </button>
                          <button type="button" className="text-button" onClick={() => void cancelAdd()}>
                            إلغاء
                          </button>
                        </div>
                      </form>
                    </section>
                  )}

                  {/* Edit Form */}
                  {editingConfig && !isAdding && (
                    <section className="upload-panel" style={{ border: "2px solid var(--green)", marginBottom: 24 }}>
                      <h3 style={{ margin: "0 0 10px" }}>تعديل مهمة: {editingConfig.task_label}</h3>
                      <form onSubmit={handleSaveConfig} style={{ display: "grid", gap: 12 }}>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                          <div>
                            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>اسم النموذج (Model):</label>
                            <input
                              required
                              value={modelInput}
                              onChange={(e) => setModelInput(e.target.value)}
                              placeholder="مثال: gemini-3.5-flash, gemini-3.5-flash-lite"
                              style={{ width: "100%", padding: "10px", border: "1px solid var(--line)", borderRadius: 6 }}
                            />
                          </div>
                          <div>
                            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>نموذج Fallback (اختياري):</label>
                            <input
                              value={fallbackModelInput}
                              onChange={(e) => setFallbackModelInput(e.target.value)}
                              placeholder="مثال: gemini-3.5-flash-lite"
                              style={{ width: "100%", padding: "10px", border: "1px solid var(--line)", borderRadius: 6 }}
                            />
                          </div>
                        </div>

                        <div>
                          <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>
                            مفتاح Gemini API خاص (اتركه فارغاً للحفاظ على المفتاح الحالي):
                          </label>
                          <input
                            type="password"
                            value={apiKeyInput}
                            onChange={(e) => setApiKeyInput(e.target.value)}
                            placeholder={editingConfig.has_custom_api_key ? "مفتاح خاص مُعيّن حالياً" : "المفتاح العام للمنصة"}
                            style={{ width: "100%", padding: "10px", border: "1px solid var(--line)", borderRadius: 6 }}
                          />
                        </div>

                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                          <div>
                            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>درجة الحرارة (0.0–1.0):</label>
                            <input
                              type="number"
                              step="0.05"
                              min="0"
                              max="1"
                              value={tempInput}
                              onChange={(e) => setTempInput(Number(e.target.value))}
                              style={{ width: "100%", padding: "10px", border: "1px solid var(--line)", borderRadius: 6 }}
                            />
                          </div>
                          <div>
                            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>الحد الأقصى للتوكنز:</label>
                            <input
                              type="number"
                              min="100"
                              max="16000"
                              value={tokensInput}
                              onChange={(e) => setTokensInput(Number(e.target.value))}
                              style={{ width: "100%", padding: "10px", border: "1px solid var(--line)", borderRadius: 6 }}
                            />
                          </div>
                          <div>
                            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>وصف المهمة:</label>
                            <input
                              value={descInput}
                              onChange={(e) => setDescInput(e.target.value)}
                              style={{ width: "100%", padding: "10px", border: "1px solid var(--line)", borderRadius: 6 }}
                            />
                          </div>
                        </div>

                        {testResult && (
                          <p style={{
                            padding: "8px 12px",
                            borderRadius: 6,
                            background: testResult.startsWith("✅") ? "#e7f0e5" : "#fff0ed",
                            fontSize: 13,
                            margin: 0,
                          }}>
                            {testResult}
                          </p>
                        )}

                        <div style={{ display: "flex", gap: 10 }}>
                          <button className="session-start" type="submit" disabled={busy}>
                            {busy ? "جارٍ الحفظ…" : "حفظ التعديلات"}
                          </button>
                          <button
                            type="button"
                            className="session-start"
                            style={{ margin: 0 }}
                            onClick={() => void handleTestModel()}
                            disabled={busy || !modelInput.trim()}
                          >
                            اختبار اتصال النموذج الآن
                          </button>
                          <button type="button" className="text-button" onClick={() => setEditingConfig(null)}>
                            إلغاء
                          </button>
                        </div>
                      </form>
                    </section>
                  )}

                  {/* Simplified Table View */}
                  <div className="admin-table-container">
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>نوع المهمة</th>
                          <th>النموذج</th>
                          <th>مفتاح API</th>
                          <th>الحالة</th>
                          <th>إجراءات</th>
                        </tr>
                      </thead>
                      <tbody>
                        {aiConfigs.map((cfg) => (
                          <tr key={cfg.task_type}>
                            <td>
                              <strong>{cfg.task_label}</strong>
                              <br />
                              <small style={{ color: "var(--muted)" }}>{cfg.task_type}</small>
                            </td>
                            <td>
                              <span className="token-badge">{cfg.model_name}</span>
                              <small style={{ display: "block", color: "var(--muted)", marginTop: 2 }}>
                                temp {cfg.temperature} · {cfg.max_output_tokens}tok
                              </small>
                            </td>
                            <td>
                              {cfg.has_custom_api_key ? (
                                <code style={{ fontSize: 12 }}>
                                  {cfg.api_key?.slice(0, 4)}...{cfg.api_key?.slice(-4) || "****"}
                                </code>
                              ) : (
                                <span style={{ color: "var(--muted)", fontSize: 12 }}>المفتاح العام</span>
                              )}
                            </td>
                            <td>
                              <span style={{
                                fontSize: 12,
                                padding: "3px 8px",
                                borderRadius: 12,
                                fontWeight: 700,
                                background: cfg.is_active ? "#e7f0e5" : "#f0f0f0",
                                color: cfg.is_active ? "#2e6930" : "#777",
                                cursor: "pointer",
                              }}
                                onClick={() => void handleToggleConfig(cfg)}
                                title={cfg.is_active ? "نقر لتعطيل" : "نقر لتفعيل"}
                              >
                                {cfg.is_active ? "نشط 🟢" : "معطل ⚪"}
                              </span>
                            </td>
                            <td>
                              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                                <button
                                  className="text-button"
                                  style={{ fontSize: 12, padding: "4px 8px" }}
                                  onClick={() => void startEditConfig(cfg)}
                                  disabled={!!isAdding}
                                >
                                  تعديل
                                </button>
                                <button
                                  className="text-button"
                                  style={{ fontSize: 12, padding: "4px 8px", color: "#9b3f32" }}
                                  onClick={() => void handleDeleteConfig(cfg)}
                                  disabled={busy}
                                >
                                  حذف
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}'''

new_content = content[:start_idx] + new_tab + '\n\n' + content[end_idx + len(end_marker):]

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f'Replaced AI tab. File now has {len(new_content)} chars.')
