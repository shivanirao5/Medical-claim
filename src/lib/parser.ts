import Tesseract from 'tesseract.js';
import * as pdfjsLib from 'pdfjs-dist';
import { AnalysisItem } from '@/components/Dashboard';

// Configure PDF.js worker with fallback
try {
  // Try to use the CDN version first
  pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.worker.min.js';
} catch (error) {
  console.warn('PDF worker CDN setup failed, trying local fallback');
  try {
    pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
      'pdfjs-dist/build/pdf.worker.min.js',
      import.meta.url
    ).toString();
  } catch (fallbackError) {
    console.warn('PDF worker setup failed:', fallbackError);
  }
}

interface ExtractedData {
  bills: BillItem[];
  prescriptions: PrescriptionItem[];
  patientInfo: PatientInfo;
  structuredContent: StructuredDocument;
}

interface BillItem {
  name: string;
  price: number;
  category?: string;
}

interface PrescriptionItem {
  name: string;
  type: 'medicine' | 'test' | 'procedure';
}

interface PatientInfo {
  name: string;
  relation: 'Self' | 'Spouse' | 'Child' | 'Parent' | 'Sibling' | 'Other';
  age?: number;
  gender?: 'Male' | 'Female' | 'Other';
}

interface StructuredDocument {
  document_title: string;
  sections: DocumentSection[];
  tables: DocumentTable[];
  metadata: DocumentMetadata;
  content_analysis: ContentAnalysis;
}

interface DocumentSection {
  section_name: string;
  content: string;
  hierarchy_level: number;
  page_number?: number;
}

interface DocumentTable {
  table_name: string;
  headers: string[];
  rows: string[][];
  page_number?: number;
}

interface DocumentMetadata {
  page_count: number;
  extraction_timestamp: string;
  file_name: string;
  file_type: string;
  file_size: number;
  text_quality_score: number;
}

interface ContentAnalysis {
  key_identifiers: KeyIdentifier[];
  important_dates: ImportantDate[];
  amounts: Amount[];
  parties_involved: Party[];
  document_type: string;
  confidence_score: number;
}

interface KeyIdentifier {
  type: 'bill_number' | 'reference_id' | 'policy_number' | 'invoice_number' | 'claim_number' | 'patient_id' | 'other';
  value: string;
  context: string;
  confidence: number;
}

interface ImportantDate {
  type: 'billing_date' | 'due_date' | 'service_date' | 'admission_date' | 'discharge_date' | 'issue_date' | 'other';
  value: string;
  context: string;
  confidence: number;
}

interface Amount {
  type: 'total' | 'subtotal' | 'tax' | 'discount' | 'charge' | 'balance' | 'paid' | 'due' | 'other';
  value: number;
  currency: string;
  context: string;
  confidence: number;
}

interface Party {
  type: 'issuer' | 'recipient' | 'provider' | 'patient' | 'insurer' | 'hospital' | 'doctor' | 'pharmacy' | 'other';
  name: string;
  details?: string;
  context: string;
  confidence: number;
}

interface Section {
  title: string;
  content: string;
  key_identifiers: string[];
  dates: string[];
  amounts: number[];
  parties_involved: string[];
}

interface Table {
  headers: string[];
  rows: string[][];
}

interface Metadata {
  creation_date: string;
  last_modified: string;
  file_info: {
    name: string;
    size: number;
    type: string;
  };
  processing_info: {
    text_quality: { quality: string; score: number };
    extracted_sections: number;
    extracted_tables: number;
    total_identifiers: number;
    total_dates: number;
    total_amounts: number;
    total_parties: number;
  };
}

interface StructuredContent {
  document_title: string;
  sections: Section[];
  tables: Table[];
  metadata: Metadata;
}

export class DocumentParser {
  private static instance: DocumentParser;
  private worker: Tesseract.Worker | null = null;

  static getInstance(): DocumentParser {
    if (!DocumentParser.instance) {
      DocumentParser.instance = new DocumentParser();
    }
    return DocumentParser.instance;
  }

  private async initializeWorker(): Promise<Tesseract.Worker> {
    if (this.worker) {
      return this.worker;
    }

    try {
      console.log('Creating Tesseract worker...');
      this.worker = await Tesseract.createWorker('eng', 1, {
        logger: m => {
          if (m.status === 'recognizing text') {
            console.log(`OCR Progress: ${Math.round(m.progress * 100)}%`);
          }
        }
      });

      console.log('Tesseract worker initialized successfully');
      return this.worker;
    } catch (error) {
      console.error('Failed to initialize Tesseract worker:', error);
      throw new Error(`OCR initialization failed: ${error.message}. Please check your internet connection and try again.`);
    }
  }

  async extractTextFromFile(file: File): Promise<string> {
    try {
      console.log(`🔍 Starting text extraction for: ${file.name}`);
      console.log(`📄 File type: ${file.type}, Size: ${(file.size / 1024).toFixed(1)} KB`);

      // If a backend is available (development proxy /api), prefer server-side extraction
      try {
        if (typeof window !== 'undefined' && (file.type === 'application/pdf' || file.type.startsWith('image/') || file.type === 'text/plain')) {
          console.log('🔄 Attempting backend extraction...');
          const form = new FormData();
          form.append('file', file, file.name);

          const resp = await fetch('/api/extract', {
            method: 'POST',
            body: form
          });

          if (resp.ok) {
            const json = await resp.json();
            if (json && json.raw_text && json.raw_text.trim().length > 0) {
              console.log('✅ Using backend-extracted text:', json.raw_text.length, 'characters');
              return json.raw_text as string;
            }
            // If backend returned structured claim, try common fields
            if (json && typeof json === 'object') {
              if (Array.isArray(json.items) && json.items.length > 0) {
                console.log('✅ Using backend-parsed items');
                return json.items.map((it: any) => it.description || '').join('\n');
              }
              // If raw_text exists but is empty/whitespace, still try client-side
              if (json.raw_text !== undefined) {
                console.log('⚠️ Backend returned empty text, falling back to client extraction');
              }
            }
          } else {
            console.warn('❌ Backend extract returned non-OK status:', resp.status, 'falling back to client extraction');
          }
        }
      } catch (e) {
        console.warn('❌ Backend extract failed or not reachable, falling back to client extraction:', e);
      }

      if (file.type === 'application/pdf') {
        console.log('📋 Detected PDF file, using PDF text extraction...');
        return await this.extractTextFromPDF(file);
      } else if (file.type.startsWith('image/')) {
        console.log('🖼️  Detected image file, using OCR extraction...');
        return await this.extractTextFromImage(file);
      } else {
        throw new Error(`Unsupported file type: ${file.type}. Please upload PDF or image files (JPG, PNG, etc.)`);
      }
    } catch (error) {
      console.error('❌ Error extracting text from file:', error);
      throw error;
    }
  }

  private async extractTextFromPDF(file: File): Promise<string> {
    try {
      console.log(`Starting PDF extraction for ${file.name}...`);
      const arrayBuffer = await file.arrayBuffer();
      console.log(`File size: ${arrayBuffer.byteLength} bytes`);

      const pdf = await pdfjsLib.getDocument({
        data: arrayBuffer,
        verbosity: 0 // Reduce console noise
      }).promise;

      console.log(`PDF loaded with ${pdf.numPages} pages`);
      let fullText = '';

      for (let i = 1; i <= Math.min(pdf.numPages, 20); i++) { // Limit to first 20 pages
        try {
          const page = await pdf.getPage(i);
          const textContent = await page.getTextContent();
          const pageText = textContent.items
            .map((item) => 'str' in item ? item.str : '')
            .join(' ');
          fullText += pageText + '\n';
          console.log(`Page ${i} extracted: ${pageText.length} characters`);
        } catch (pageError) {
          console.warn(`Failed to extract page ${i}:`, pageError);
          // Continue with other pages
        }
      }

      const cleanText = fullText.trim();
      console.log(`PDF extraction complete. Total text length: ${cleanText.length}`);

      // If PDF text extraction yielded very little text, it might be a scanned PDF
      if (cleanText.length < 100) {
        console.log('PDF appears to be scanned or has minimal text, attempting OCR fallback...');
        try {
          const ocrText = await this.extractTextFromImage(file);
          if (ocrText.length > cleanText.length) {
            console.log(`OCR fallback successful: ${ocrText.length} characters extracted`);
            return ocrText;
          }
        } catch (ocrError) {
          console.warn('OCR fallback failed:', ocrError);
        }
      }

      return cleanText;
    } catch (error) {
      console.error('PDF extraction failed:', error);
      // Fallback to OCR for PDFs that can't be read directly
      console.log('Attempting OCR fallback for PDF...');
      return await this.extractTextFromImage(file);
    }
  }

  private async extractTextFromImage(file: File): Promise<string> {
    try {
      console.log(`Starting OCR for ${file.name}...`);

      // Ensure worker is initialized
      if (!this.worker) {
        console.log('Initializing Tesseract worker...');
        this.worker = await Tesseract.createWorker('eng', 1, {
          logger: m => {
            if (m.status === 'recognizing text') {
              console.log(`OCR Progress: ${Math.round(m.progress * 100)}%`);
            }
          }
        });

        // Configure for better medical document recognition
        await this.worker.setParameters({
          tessedit_char_whitelist: '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz₹$.,/-()[]{}@#%&*+=:;"\'? ',
          tessedit_pageseg_mode: Tesseract.PSM.AUTO_OSD,
          tessedit_ocr_engine_mode: Tesseract.OEM.LSTM_ONLY,
          // Enhanced settings for scanned medical documents
          textord_min_linesize: 2.5,
          tessedit_create_hocr: 0,
          tessedit_create_tsv: 0,
          tessedit_create_pdf: 0,
        });

        console.log('Tesseract worker initialized with medical document settings');
      }

      console.log('Starting OCR recognition...');
      const { data: { text } } = await this.worker.recognize(file);
      const cleanText = text.trim();

      console.log(`OCR complete. Text length: ${cleanText.length}`);
      if (cleanText.length > 0) {
        console.log(`OCR result preview: ${cleanText.substring(0, 200)}...`);
      }

      // Post-process the extracted text for better medical document handling
      const processedText = this.postProcessMedicalText(cleanText);

      return processedText;
    } catch (error) {
      console.error('OCR failed:', error);
      throw new Error(`Failed to extract text from image: ${error.message}`);
    }
  }

  private postProcessMedicalText(text: string): string {
    return text
      // Fix common OCR errors in medical documents
      .replace(/₹\s*(\d)/g, '₹$1') // Fix rupee symbol spacing
      .replace(/Rs\s*\.\s*/g, 'Rs.') // Fix Rs. abbreviation
      .replace(/(\d)\s*,\s*(\d)/g, '$1,$2') // Fix number formatting
      .replace(/\s+/g, ' ') // Normalize multiple spaces
      .replace(/(\w)\s*\n\s*(\w)/g, '$1 $2') // Fix line breaks in words
      .replace(/\n\s*\n/g, '\n') // Remove excessive line breaks
      // Fix common medical abbreviations
      .replace(/\btab\b/gi, 'Tablet')
      .replace(/\bcap\b/gi, 'Capsule')
      .replace(/\binj\b/gi, 'Injection')
      .replace(/\bdr\b/gi, 'Dr.')
      .replace(/\bmg\b/gi, 'mg')
      .replace(/\bml\b/gi, 'ml')
      .trim();
  }

  private validateTextQuality(text: string): { quality: string; score: number } {
    const lines = text.split('\n').filter(line => line.trim().length > 0);
    let score = 0;

    // Length score (0-30 points)
    if (text.length > 1000) score += 30;
    else if (text.length > 500) score += 20;
    else if (text.length > 100) score += 10;

    // Line count score (0-20 points)
    if (lines.length > 20) score += 20;
    else if (lines.length > 10) score += 15;
    else if (lines.length > 5) score += 10;

    // Medical keywords score (0-30 points)
    const medicalKeywords = ['patient', 'doctor', 'medicine', 'test', 'prescription', 'bill', 'amount', 'rs', '₹'];
    const foundKeywords = medicalKeywords.filter(keyword =>
      text.toLowerCase().includes(keyword.toLowerCase())
    );
    score += Math.min(foundKeywords.length * 3, 30);

    // Structure score (0-20 points)
    const hasNumbers = /\d/.test(text);
    const hasCurrency = /[₹$]|\brs\b/i.test(text);
    const hasDates = /\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4}/.test(text);

    if (hasNumbers) score += 7;
    if (hasCurrency) score += 7;
    if (hasDates) score += 6;

    // Determine quality level
    let quality = 'Poor';
    if (score >= 80) quality = 'Excellent';
    else if (score >= 60) quality = 'Good';
    else if (score >= 40) quality = 'Fair';
    else if (score >= 20) quality = 'Poor';

    return { quality, score };
  }

  parseBillText(text: string): BillItem[] {
    const items: BillItem[] = [];
    const lines = text.split('\n').filter(line => line.trim().length > 0);

    console.log(`Parsing bill text with ${lines.length} lines`);

    // Enhanced bill patterns for better extraction
    const pricePatterns = [
      // Indian Rupee patterns
      /(.+?)\s+(?:Rs\.?|₹|INR)\s*(\d+(?:,\d{3})*(?:\.\d{2})?)/gi,
      /(.+?)\s+(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:Rs\.?|₹|INR)/gi,
      // General price patterns
      /(.+?)\s*[:-=]\s*(?:Rs\.?|₹|INR)?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)/gi,
      // Table format patterns
      /^(.+?)\s+(\d+(?:,\d{3})*(?:\.\d{2})?)$/gm,
      // Amount patterns with decimal
      /(.+?)\s+(\d+\.\d{2})/gi,
      // Simple number patterns
      /(.+?)\s+(\d+)/gi
    ];

    // Medical keywords for better categorization
    const medicineKeywords = [
      'tablet', 'capsule', 'syrup', 'injection', 'drops', 'cream', 'ointment', 'pill',
      'medicine', 'drug', 'pharmaceutical', 'paracetamol', 'ibuprofen', 'aspirin',
      'antibiotic', 'vitamin', 'supplement', 'dosage', 'medication', 'tab', 'cap'
    ];

    const testKeywords = [
      'test', 'scan', 'x-ray', 'mri', 'ct', 'blood', 'urine', 'ecg', 'ultrasound',
      'pathology', 'laboratory', 'diagnosis', 'screening', 'biopsy', 'report',
      'investigation', 'examination', 'cbc', 'esr', 'fbs', 'ppbs', 'hb', 'hba1c'
    ];

    const procedureKeywords = [
      'consultation', 'surgery', 'procedure', 'therapy', 'treatment', 'operation',
      'checkup', 'visit', 'appointment', 'examination', 'assessment', 'evaluation',
      'physiotherapy', 'follow-up', 'review', 'fee', 'charge'
    ];

    let foundItems = 0;

    for (const line of lines) {
      // Skip header lines or total lines
      const lowerLine = line.toLowerCase();
      if (lowerLine.includes('total') ||
          lowerLine.includes('amount') ||
          lowerLine.includes('bill') ||
          lowerLine.includes('grand total') ||
          lowerLine.includes('net amount') ||
          lowerLine.includes('date') ||
          lowerLine.includes('patient') ||
          lowerLine.includes('doctor') ||
          line.trim().length < 3) {
        continue;
      }

      for (const pattern of pricePatterns) {
        pattern.lastIndex = 0; // Reset regex
        const matches = Array.from(line.matchAll(pattern));

        for (const match of matches) {
          const itemName = match[1]?.trim();
          const priceStr = match[2]?.replace(/,/g, '');
          const price = parseFloat(priceStr);

          if (itemName && !isNaN(price) && price > 0 && itemName.length > 2) {
            // Clean up item name
            const cleanName = itemName
              .replace(/^\d+\.?\s*/, '') // Remove leading numbers
              .replace(/^[-.*]\s*/, '') // Remove leading dashes/dots
              .replace(/\s+/g, ' ') // Normalize spaces
              .trim();

            if (cleanName.length > 2 && cleanName.length < 100) { // Reasonable length check
              // Determine category based on keywords
              let category = 'General';
              const lowerName = cleanName.toLowerCase();

              if (medicineKeywords.some(keyword => lowerName.includes(keyword))) {
                category = 'Medicine';
              } else if (testKeywords.some(keyword => lowerName.includes(keyword))) {
                category = 'Test';
              } else if (procedureKeywords.some(keyword => lowerName.includes(keyword))) {
                category = 'Procedure';
              }

              items.push({
                name: cleanName,
                price,
                category
              });

              foundItems++;
              console.log(`Found bill item: ${cleanName} - ₹${price} (${category})`);
            }
          }
        }
      }
    }

    console.log(`Bill parsing complete: ${foundItems} items found`);

    // Remove duplicates based on similar names and prices
    const deduplicated = this.deduplicateItems(items);
    console.log(`After deduplication: ${deduplicated.length} unique items`);

    return deduplicated;
  }

  parsePrescriptionText(text: string): PrescriptionItem[] {
    const items: PrescriptionItem[] = [];
    const lines = text.split('\n').filter(line => line.trim().length > 0);

    // Enhanced prescription patterns
    const medicinePatterns = [
      // Common medicine formats
      /(?:Tab\.?|Tablet|Cap\.?|Capsule|Syrup|Inj\.?|Injection)\s+([A-Za-z0-9\s-]+)/gi,
      /(\w+(?:\s+\w+)*)\s+(?:\d+mg|\d+ml|\d+%|\d+g)/gi,
      // Medicine with brand names
      /^(\w+(?:\s+\w+)*)\s*(?:\([^)]+\))?\s*(?:\d+mg|\d+ml|\d+%|\d+g)?/gmi,
      // R/ or Rx prescriptions
      /(?:R\/|Rx)\s*:?\s*([A-Za-z0-9\s-]+)/gi
    ];

    const testPatterns = [
      // Test orders
      /(?:Test|Lab|Investigation|Order):\s*([A-Za-z0-9\s-,]+)/gi,
      /(Blood\s+\w+|Urine\s+\w+|X-Ray|MRI|CT\s+Scan|Ultrasound|ECG|EKG)/gi,
      // Pathology tests
      /(CBC|ESR|FBS|PPBS|HbA1c|Lipid\s+Profile|Liver\s+Function|Kidney\s+Function)/gi
    ];

    const procedurePatterns = [
      /(?:Procedure|Treatment|Therapy):\s*([A-Za-z0-9\s-,]+)/gi,
      /(Physiotherapy|Consultation|Follow-up|Review)/gi
    ];

    // Extract medicines
    for (const line of lines) {
      // Skip empty or very short lines
      if (line.trim().length < 3) continue;

      for (const pattern of medicinePatterns) {
        pattern.lastIndex = 0; // Reset regex
        const matches = Array.from(line.matchAll(pattern));
        for (const match of matches) {
          const name = match[1]?.trim();
          if (name && name.length > 2) {
            const cleanName = this.cleanItemName(name);
            if (cleanName.length > 2) {
              items.push({
                name: cleanName,
                type: 'medicine'
              });
            }
          }
        }
      }

      // Extract tests
      for (const pattern of testPatterns) {
        pattern.lastIndex = 0;
        const matches = Array.from(line.matchAll(pattern));
        for (const match of matches) {
          const name = match[1] || match[0];
          if (name) {
            if (name.includes(',')) {
              // Multiple tests in one line
              const tests = name.split(',').map(t => t.trim());
              tests.forEach(test => {
                if (test.length > 2) {
                  items.push({
                    name: this.cleanItemName(test),
                    type: 'test'
                  });
                }
              });
            } else {
              const cleanName = this.cleanItemName(name);
              if (cleanName.length > 2) {
                items.push({
                  name: cleanName,
                  type: 'test'
                });
              }
            }
          }
        }
      }

      // Extract procedures
      for (const pattern of procedurePatterns) {
        pattern.lastIndex = 0;
        const matches = Array.from(line.matchAll(pattern));
        for (const match of matches) {
          const name = match[1] || match[0];
          if (name) {
            const cleanName = this.cleanItemName(name);
            if (cleanName.length > 2) {
              items.push({
                name: cleanName,
                type: 'procedure'
              });
            }
          }
        }
      }
    }

    return this.deduplicatePrescriptionItems(items);
  }

  extractPatientInfo(text: string): PatientInfo {
    const lines = text.split('\n').filter(line => line.trim().length > 0);
    let patientName = '';
    let relation: PatientInfo['relation'] = 'Self';
    let age: number | undefined;
    let gender: PatientInfo['gender'] | undefined;

    console.log('Extracting patient information from document...');

    // Patient name patterns
    const namePatterns = [
      /(?:Patient|Name|Patient\s+Name)\s*:?\s*([A-Za-z\s.]+)/gi,
      /(?:Name\s+of\s+Patient|Patient\s+Details)\s*:?\s*([A-Za-z\s.]+)/gi,
      /(?:Beneficiary|Insured)\s*:?\s*([A-Za-z\s.]+)/gi,
      // Common Indian name patterns
      /(?:Mr\.|Mrs\.|Ms\.|Dr\.)\s+([A-Za-z\s.]+)/gi
    ];

    // Relation patterns
    const relationPatterns = [
      /(?:Relation|Relationship)\s*:?\s*(Self|Spouse|Wife|Husband|Child|Son|Daughter|Father|Mother|Parent|Sibling|Brother|Sister)/gi,
      /(?:Dependent|Dependant)\s*:?\s*(Self|Spouse|Wife|Husband|Child|Son|Daughter|Father|Mother|Parent|Sibling|Brother|Sister)/gi,
      /(?:Family\s+Member)\s*:?\s*(Self|Spouse|Wife|Husband|Child|Son|Daughter|Father|Mother|Parent|Sibling|Brother|Sister)/gi
    ];

    // Age patterns
    const agePatterns = [
      /(?:Age|Years?)\s*:?\s*(\d+)/gi,
      /(\d+)\s*(?:years?|yrs?|yo)/gi,
      /(?:DOB|Date\s+of\s+Birth)\s*:?\s*(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})/gi
    ];

    // Gender patterns
    const genderPatterns = [
      /(?:Gender|Sex)\s*:?\s*(Male|Female|M|F)/gi,
      /(?:Mr\.|Sir)/gi, // Male indicators
      /(?:Mrs\.|Ms\.|Miss)/gi // Female indicators
    ];

    // Extract patient name
    for (const line of lines) {
      for (const pattern of namePatterns) {
        pattern.lastIndex = 0;
        const match = pattern.exec(line);
        if (match && match[1]) {
          patientName = match[1].trim();
          console.log(`Found patient name: ${patientName}`);
          break;
        }
      }
      if (patientName) break;
    }

    // Extract relation
    for (const line of lines) {
      for (const pattern of relationPatterns) {
        pattern.lastIndex = 0;
        const match = pattern.exec(line);
        if (match && match[1]) {
          const foundRelation = match[1].toLowerCase();
          switch (foundRelation) {
            case 'wife':
            case 'husband':
              relation = 'Spouse';
              break;
            case 'son':
            case 'daughter':
              relation = 'Child';
              break;
            case 'father':
            case 'mother':
              relation = 'Parent';
              break;
            case 'brother':
            case 'sister':
              relation = 'Sibling';
              break;
            case 'self':
              relation = 'Self';
              break;
            default:
              relation = 'Other';
          }
          console.log(`Found relation: ${relation}`);
          break;
        }
      }
      if (relation !== 'Self') break;
    }

    // Extract age
    for (const line of lines) {
      for (const pattern of agePatterns) {
        pattern.lastIndex = 0;
        const match = pattern.exec(line);
        if (match) {
          if (match[1]) {
            age = parseInt(match[1]);
          } else if (match[1] && match[2] && match[3]) {
            // DOB pattern - calculate age
            const birthYear = parseInt(match[3]);
            const currentYear = new Date().getFullYear();
            age = currentYear - birthYear;
          }
          if (age && age > 0 && age < 120) {
            console.log(`Found age: ${age}`);
            break;
          }
        }
      }
      if (age) break;
    }

    // Extract gender
    for (const line of lines) {
      for (const pattern of genderPatterns) {
        pattern.lastIndex = 0;
        const match = pattern.exec(line);
        if (match && match[1]) {
          const foundGender = match[1].toUpperCase();
          if (foundGender === 'M' || foundGender === 'MALE' || foundGender === 'MR.' || foundGender === 'SIR') {
            gender = 'Male';
          } else if (foundGender === 'F' || foundGender === 'FEMALE' || foundGender === 'MRS.' || foundGender === 'MS.' || foundGender === 'MISS') {
            gender = 'Female';
          }
          console.log(`Found gender: ${gender}`);
          break;
        }
      }
      if (gender) break;
    }

    // If no patient name found, try to extract from common patterns
    if (!patientName) {
      const commonPatterns = [
        /^([A-Z][a-z]+\s+[A-Z][a-z]+)$/gm, // Full name pattern
        /(?:For|Patient)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)/gi
      ];

      for (const line of lines) {
        for (const pattern of commonPatterns) {
          pattern.lastIndex = 0;
          const match = pattern.exec(line);
          if (match && match[1] && match[1].length > 3) {
            patientName = match[1].trim();
            console.log(`Found patient name from common pattern: ${patientName}`);
            break;
          }
        }
        if (patientName) break;
      }
    }

    // Default values if nothing found
    if (!patientName) {
      patientName = 'Patient Name Not Found';
      console.log('Patient name not found in document');
    }

    console.log(`Patient info extraction complete: ${patientName}, ${relation}, Age: ${age}, Gender: ${gender}`);

    return {
      name: patientName,
      relation,
      age,
      gender
    };
  }

  compareAndAnalyze(bills: BillItem[], prescriptions: PrescriptionItem[], patientInfo?: PatientInfo): AnalysisItem[] {
    const analysisResults: AnalysisItem[] = [];

    bills.forEach((billItem, index) => {
      const isAdmissible = this.isItemAdmissible(billItem, prescriptions, patientInfo);

      // Policy: consultation fee cap
      const isConsultation = /consult|consultation|visit|doctor|fee|appointment|consulting/i.test(billItem.name) || (billItem.category === 'Procedure');
      const CONSULTATION_CAP = 300;

      let approvedPrice = 0;
      let reimbursementAmount = 0;

      if (isAdmissible) {
        if (isConsultation) {
          approvedPrice = Math.min(billItem.price, CONSULTATION_CAP);
        } else {
          approvedPrice = billItem.price;
        }
        // Default reimbursement equals approved price (user can edit in UI)
        reimbursementAmount = approvedPrice;
      } else {
        approvedPrice = 0;
        reimbursementAmount = 0;
      }

      analysisResults.push({
        id: `item-${index}`,
        itemName: billItem.name,
        claimedPrice: billItem.price,
        status: isAdmissible ? 'Admissible' : 'Not Admissible',
        approvedPrice,
        reimbursementAmount,
        category: billItem.category
      });
    });

    return analysisResults;
  }

  private isItemAdmissible(billItem: BillItem, prescriptions: PrescriptionItem[], patientInfo?: PatientInfo): boolean {
    // Policy: allowed relations
    const allowedRelations: PatientInfo['relation'][] = ['Self', 'Spouse', 'Child', 'Parent'];
    const relation = patientInfo?.relation || 'Self';

    if (!allowedRelations.includes(relation)) {
      // Not covered for reimbursement
      return false;
    }

    const billName = this.normalizeItemName(billItem.name);

    // If consultation/procedure-like fee and relation is covered, approve (subject to cap applied elsewhere)
    const isConsultation = /consult|consultation|visit|doctor|fee|appointment|consulting/i.test(billItem.name) || (billItem.category === 'Procedure');
    if (isConsultation) return true;

    return prescriptions.some(prescription => {
      const prescriptionName = this.normalizeItemName(prescription.name);

      // Check for exact match
      if (billName === prescriptionName) {
        return true;
      }

      // Check for partial matches with enhanced scoring
      const billWords = billName.split(' ').filter(word => word.length > 2);
      const prescriptionWords = prescriptionName.split(' ').filter(word => word.length > 2);

      if (billWords.length === 0 || prescriptionWords.length === 0) {
        return false;
      }

      // Calculate similarity score
      let matchScore = 0;
      const totalWords = Math.max(billWords.length, prescriptionWords.length);

      billWords.forEach(billWord => {
        prescriptionWords.forEach(prescWord => {
          // Exact word match
          if (billWord === prescWord) {
            matchScore += 1;
          }
          // Partial word match (contains)
          else if (billWord.length > 3 && prescWord.length > 3) {
            if (billWord.includes(prescWord) || prescWord.includes(billWord)) {
              matchScore += 0.7;
            }
            // Levenshtein-like similarity for common medical terms
            else if (this.calculateSimilarity(billWord, prescWord) > 0.8) {
              matchScore += 0.6;
            }
          }
        });
      });

      // Different thresholds for different types
      const threshold = prescription.type === 'medicine' ? 0.4 : 0.3;
      const similarityRatio = matchScore / totalWords;

      return similarityRatio >= threshold;
    });
  }

  private normalizeItemName(name: string): string {
    return name
      .toLowerCase()
      .replace(/[^\w\s]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  private cleanItemName(name: string): string {
    return name
      .replace(/^[^\w\s-]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  private deduplicateItems(items: BillItem[]): BillItem[] {
    const seen = new Set<string>();
    return items.filter(item => {
      const key = `${this.normalizeItemName(item.name)}-${item.price}`;
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }

  private deduplicatePrescriptionItems(items: PrescriptionItem[]): PrescriptionItem[] {
    const seen = new Set<string>();
    return items.filter(item => {
      const key = this.normalizeItemName(item.name);
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }

  private calculateSimilarity(str1: string, str2: string): number {
    const longer = str1.length > str2.length ? str1 : str2;
    const shorter = str1.length > str2.length ? str2 : str1;
    
    if (longer.length === 0) {
      return 1.0;
    }
    
    const editDistance = this.levenshteinDistance(longer, shorter);
    return (longer.length - editDistance) / longer.length;
  }

  private levenshteinDistance(str1: string, str2: string): number {
    const matrix = [];
    
    for (let i = 0; i <= str2.length; i++) {
      matrix[i] = [i];
    }
    
    for (let j = 0; j <= str1.length; j++) {
      matrix[0][j] = j;
    }
    
    for (let i = 1; i <= str2.length; i++) {
      for (let j = 1; j <= str1.length; j++) {
        if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
          matrix[i][j] = matrix[i - 1][j - 1];
        } else {
          matrix[i][j] = Math.min(
            matrix[i - 1][j - 1] + 1,
            matrix[i][j - 1] + 1,
            matrix[i - 1][j] + 1
          );
        }
      }
    }
    
    return matrix[str2.length][str1.length];
  }

  async processDocuments(files: File[]): Promise<{ analysisResults: AnalysisItem[], patientInfo: PatientInfo, structuredContent: StructuredContent[] }> {
    try {
      console.log('Starting document processing...');
      console.log(`Processing ${files.length} files:`, files.map(f => `${f.name} (${f.type})`));

      // Extract text from all files
      const allTexts: string[] = [];
      const fileResults: { fileName: string; text: string; billItems: BillItem[]; prescriptionItems: PrescriptionItem[]; patientInfo: PatientInfo; structuredContent: StructuredContent }[] = [];

      for (const file of files) {
        console.log(`\n=== Processing file: ${file.name} ===`);
        console.log(`File type: ${file.type}, Size: ${(file.size / 1024).toFixed(1)} KB`);

        try {
          const text = await this.extractTextFromFile(file);
          console.log(`Raw extracted text length: ${text.length}`);
          console.log(`Text preview: ${text.substring(0, 200)}...`);

          if (text && text.trim().length > 5) { // Lower threshold for medical documents
            allTexts.push(text);

            // Validate text quality
            const textQuality = this.validateTextQuality(text);
            console.log(`📊 Text quality assessment: ${textQuality.quality} (${textQuality.score}/100)`);

            // Parse this specific file
            const billItems = this.parseBillText(text);
            const prescriptionItems = this.parsePrescriptionText(text);
            const patientInfo = this.extractPatientInfo(text);
            const structuredContent = this.extractStructuredContent(text, file.name);

            fileResults.push({
              fileName: file.name,
              text: text,
              billItems: billItems,
              prescriptionItems: prescriptionItems,
              patientInfo: patientInfo,
              structuredContent: structuredContent
            });

            console.log(`✅ Successfully processed ${file.name}:`);
            console.log(`   - Text length: ${text.length} characters`);
            console.log(`   - Bill items found: ${billItems.length}`);
            console.log(`   - Prescription items found: ${prescriptionItems.length}`);
            console.log(`   - Patient: ${patientInfo.name} (${patientInfo.relation})`);
          } else {
            console.warn(`⚠️  Insufficient text extracted from ${file.name} (${text.length} characters)`);
            console.warn('   This might indicate:');
            console.warn('   - Scanned document with poor quality');
            console.warn('   - Unsupported file format');
            console.warn('   - Very small or empty document');
          }
        } catch (error) {
          console.error(`❌ Failed to process ${file.name}:`, error);
        }
      }

      if (allTexts.length === 0) {
        throw new Error('No readable text could be extracted from any of the uploaded files. Please ensure your documents contain clear, readable text and try again.');
      }

      // Aggregate all bill and prescription items
      const allBillItems: BillItem[] = [];
      const allPrescriptionItems: PrescriptionItem[] = [];

      fileResults.forEach(result => {
        allBillItems.push(...result.billItems);
        allPrescriptionItems.push(...result.prescriptionItems);
      });

      console.log(`\n� Processing Summary:`);
      console.log(`- Files processed: ${fileResults.length}`);
      console.log(`- Total bill items: ${allBillItems.length}`);
      console.log(`- Total prescription items: ${allPrescriptionItems.length}`);

      // Show detailed breakdown
      fileResults.forEach(result => {
        console.log(`\n📄 ${result.fileName}:`);
        if (result.billItems.length > 0) {
          console.log(`   Bill items: ${result.billItems.map(item => `${item.name} (₹${item.price})`).join(', ')}`);
        }
        if (result.prescriptionItems.length > 0) {
          console.log(`   Prescription items: ${result.prescriptionItems.map(item => item.name).join(', ')}`);
        }
      });

      if (allBillItems.length === 0) {
        throw new Error('No bill items could be identified in the uploaded documents. Please ensure your medical bills contain item names and prices in a recognizable format.');
      }

      // Consolidate best patient info across files (used for policy checks)
      let bestPatientInfo: PatientInfo = {
        name: 'Patient Name Not Found',
        relation: 'Self'
      };

      fileResults.forEach(result => {
        const info = result.patientInfo;
        // Prefer info with actual name over "Not Found"
        if (info.name !== 'Patient Name Not Found' && bestPatientInfo.name === 'Patient Name Not Found') {
          bestPatientInfo = info;
        }
        // Prefer more complete information
        if (info.age && !bestPatientInfo.age) {
          bestPatientInfo.age = info.age;
          bestPatientInfo.gender = info.gender;
        }
      });

      console.log(`📋 Final patient info: ${bestPatientInfo.name} (${bestPatientInfo.relation})`);

      // Compare and analyze with policy awareness
      console.log('\n🔄 Starting comparison and analysis (policy-aware)...');
      const results = this.compareAndAnalyze(allBillItems, allPrescriptionItems, bestPatientInfo);

      console.log(`✅ Analysis complete: ${results.length} items processed`);
      console.log('Results:', results.map(r => `${r.itemName}: ${r.status} (claimed ₹${r.claimedPrice}, approved ₹${r.approvedPrice})`));

      // Collect all structured content
      const allStructuredContent = fileResults.map(result => result.structuredContent);

      return {
        analysisResults: results,
        patientInfo: bestPatientInfo,
        structuredContent: allStructuredContent
      };
    } catch (error) {
      console.error('❌ Error processing documents:', error);
      throw error; // Don't fallback to sample data
    }
  }

  extractStructuredContent(text: string, fileName: string): StructuredContent {
    console.log(`Extracting structured content from ${fileName}...`);

    const lines = text.split('\n').filter(line => line.trim().length > 0);
    const sections: Section[] = [];
    const tables: Table[] = [];
    const keyIdentifiers: string[] = [];
    const dates: string[] = [];
    const amounts: number[] = [];
    const partiesInvolved: string[] = [];

    // Document title detection
    let documentTitle = fileName;
    const titlePatterns = [
      /(?:Bill|Invoice|Receipt|Prescription)\s*:?\s*([^\n]+)/i,
      /(?:Medical\s+Bill|Hospital\s+Bill|Pharmacy\s+Bill)/i,
      /^([A-Z][^.\n]{10,50})/m
    ];

    for (const line of lines.slice(0, 5)) { // Check first few lines
      for (const pattern of titlePatterns) {
        const match = pattern.exec(line);
        if (match && match[1]) {
          documentTitle = match[1].trim();
          break;
        }
      }
      if (documentTitle !== fileName) break;
    }

    // Extract key identifiers (patient ID, bill number, etc.)
    const identifierPatterns = [
      /(?:Bill\s+No|Invoice\s+No|Receipt\s+No|Prescription\s+No)\s*:?\s*([A-Z0-9-]+)/gi,
      /(?:Patient\s+ID|ID\s+No|Reference\s+No)\s*:?\s*([A-Z0-9-]+)/gi,
      /(?:UHID|IPD|OPD)\s*:?\s*([A-Z0-9-]+)/gi
    ];

    for (const line of lines) {
      for (const pattern of identifierPatterns) {
        pattern.lastIndex = 0;
        const matches = Array.from(line.matchAll(pattern));
        matches.forEach(match => {
          if (match[1]) {
            keyIdentifiers.push(match[1].trim());
          }
        });
      }
    }

    // Extract dates
    const datePatterns = [
      /\b(\d{1,2})[-\/](\d{1,2})[-\/](\d{4})\b/g, // DD/MM/YYYY or DD-MM-YYYY
      /\b(\d{4})[-\/](\d{1,2})[-\/](\d{1,2})\b/g, // YYYY/MM/DD
      /(?:Date|Dated)\s*:?\s*(\d{1,2}[-\/]\d{1,2}[-\/]\d{4})/gi,
      /(?:Date|Dated)\s*:?\s*(\d{4}[-\/]\d{1,2}[-\/]\d{1,2})/gi
    ];

    for (const line of lines) {
      for (const pattern of datePatterns) {
        pattern.lastIndex = 0;
        const matches = Array.from(line.matchAll(pattern));
        matches.forEach(match => {
          dates.push(match[0]);
        });
      }
    }

    // Extract amounts
    const amountPatterns = [
      /(?:Rs\.?|₹|INR)\s*(\d+(?:,\d{3})*(?:\.\d{2})?)/gi,
      /(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:Rs\.?|₹|INR)/gi,
      /\b(\d+(?:,\d{3})*(?:\.\d{2})?)\b/g
    ];

    for (const line of lines) {
      for (const pattern of amountPatterns) {
        pattern.lastIndex = 0;
        const matches = Array.from(line.matchAll(pattern));
        matches.forEach(match => {
          const amount = parseFloat(match[1].replace(/,/g, ''));
          if (!isNaN(amount) && amount > 0) {
            amounts.push(amount);
          }
        });
      }
    }

    // Extract parties involved (doctors, hospitals, patients)
    const partyPatterns = [
      /(?:Dr\.?|Doctor)\s+([A-Za-z\s.]+)/gi,
      /(?:Hospital|Clinic|Medical\s+Center)\s*:?\s*([A-Za-z\s&.,]+)/gi,
      /(?:Patient|Beneficiary)\s*:?\s*([A-Za-z\s.]+)/gi,
      /(?:Pharmacy|Chemist)\s*:?\s*([A-Za-z\s&.,]+)/gi
    ];

    for (const line of lines) {
      for (const pattern of partyPatterns) {
        pattern.lastIndex = 0;
        const matches = Array.from(line.matchAll(pattern));
        matches.forEach(match => {
          if (match[1]) {
            partiesInvolved.push(match[1].trim());
          }
        });
      }
    }

    // Identify and extract sections
    let currentSection: Section | null = null;
    let sectionContent: string[] = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmedLine = line.trim();

      // Check if this line starts a new section
      const sectionHeaders = [
        'patient details', 'patient information', 'personal details',
        'prescription', 'medicines', 'medication', 'drugs',
        'bill details', 'billing information', 'charges', 'fee',
        'diagnosis', 'symptoms', 'complaints',
        'tests', 'investigations', 'laboratory',
        'treatment', 'procedure', 'surgery',
        'payment', 'amount', 'total', 'summary'
      ];

      const isSectionHeader = sectionHeaders.some(header =>
        trimmedLine.toLowerCase().includes(header) ||
        trimmedLine.toLowerCase().replace(/[^\w\s]/g, '').includes(header)
      );

      if (isSectionHeader || (trimmedLine.length < 50 && /^[A-Z\s]+$/.test(trimmedLine))) {
        // Save previous section if exists
        if (currentSection && sectionContent.length > 0) {
          currentSection.content = sectionContent.join('\n');
          sections.push(currentSection);
        }

        // Start new section
        currentSection = {
          title: trimmedLine,
          content: '',
          key_identifiers: [],
          dates: [],
          amounts: [],
          parties_involved: []
        };
        sectionContent = [];
      } else if (currentSection) {
        sectionContent.push(line);
      }
    }

    // Add the last section
    if (currentSection && sectionContent.length > 0) {
      currentSection.content = sectionContent.join('\n');
      sections.push(currentSection);
    }

    // If no sections found, create a default section with all content
    if (sections.length === 0) {
      sections.push({
        title: 'Document Content',
        content: text,
        key_identifiers: keyIdentifiers,
        dates: dates,
        amounts: amounts,
        parties_involved: partiesInvolved
      });
    }

    // Extract tables (simple table detection)
    const tablePatterns = [
      /^(.+?)\s+(\d+(?:,\d{3})*(?:\.\d{2})?)$/gm, // Item + Amount
      /^(.+?)\s+(\d+)\s+(.+?)\s+(\d+(?:,\d{3})*(?:\.\d{2})?)$/gm // Item + Qty + Unit + Amount
    ];

    const potentialTableRows: string[][] = [];

    for (const line of lines) {
      for (const pattern of tablePatterns) {
        pattern.lastIndex = 0;
        const match = pattern.exec(line);
        if (match) {
          const row = match.slice(1).map(cell => cell.trim());
          potentialTableRows.push(row);
        }
      }
    }

    // Group table rows if we have enough
    if (potentialTableRows.length >= 3) {
      const headers = ['Item', 'Quantity', 'Price'];
      tables.push({
        headers: headers,
        rows: potentialTableRows
      });
    }

    // Create metadata
    const metadata: Metadata = {
      creation_date: new Date().toISOString(),
      last_modified: new Date().toISOString(),
      file_info: {
        name: fileName,
        size: text.length,
        type: fileName.split('.').pop() || 'unknown'
      },
      processing_info: {
        text_quality: this.validateTextQuality(text),
        extracted_sections: sections.length,
        extracted_tables: tables.length,
        total_identifiers: keyIdentifiers.length,
        total_dates: dates.length,
        total_amounts: amounts.length,
        total_parties: partiesInvolved.length
      }
    };

    const structuredContent: StructuredContent = {
      document_title: documentTitle,
      sections: sections,
      tables: tables,
      metadata: metadata
    };

    console.log(`✅ Structured content extraction complete for ${fileName}:`);
    console.log(`   - Title: ${documentTitle}`);
    console.log(`   - Sections: ${sections.length}`);
    console.log(`   - Tables: ${tables.length}`);
    console.log(`   - Key identifiers: ${keyIdentifiers.length}`);
    console.log(`   - Dates found: ${dates.length}`);
    console.log(`   - Amounts found: ${amounts.length}`);
    console.log(`   - Parties involved: ${partiesInvolved.length}`);

    return structuredContent;
  }

  private generateSampleData(): AnalysisItem[] {
    console.log('Generating sample analysis data...');

    const sampleResults: AnalysisItem[] = [
      {
        id: 'sample-1',
        itemName: 'Paracetamol 500mg',
        claimedPrice: 25,
        status: 'Admissible',
        approvedPrice: 25,
        reimbursementAmount: 20,
        category: 'Medicine'
      },
      {
        id: 'sample-2',
        itemName: 'Blood Test - CBC',
        claimedPrice: 300,
        status: 'Admissible',
        approvedPrice: 300,
        reimbursementAmount: 250,
        category: 'Test'
      },
      {
        id: 'sample-3',
        itemName: 'Consultation Fee',
        claimedPrice: 200,
        status: 'Admissible',
        approvedPrice: 200,
        reimbursementAmount: 150,
        category: 'Procedure'
      },
      {
        id: 'sample-4',
        itemName: 'X-Ray Chest',
        claimedPrice: 400,
        status: 'Not Admissible',
        approvedPrice: 0,
        reimbursementAmount: 0,
        category: 'Test'
      }
    ];

    return sampleResults;
  }

  async cleanup(): Promise<void> {
    if (this.worker) {
      await this.worker.terminate();
      this.worker = null;
    }
  }
}