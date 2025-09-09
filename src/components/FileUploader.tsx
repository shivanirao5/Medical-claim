import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, Image, Loader2, PenTool, FileCheck } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';

interface FileUploaderProps {
  onFilesUploaded: (files: File[], isHandwritten?: boolean) => void;
  isProcessing: boolean;
}

export const FileUploader: React.FC<FileUploaderProps> = ({ onFilesUploaded, isProcessing }) => {
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [isHandwritten, setIsHandwritten] = useState(false);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setUploadedFiles(prev => [...prev, ...acceptedFiles]);
  }, []);

  const dropzone = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg']
    },
    disabled: isProcessing
  });

  const handleAnalyze = () => {
    if (uploadedFiles.length > 0) {
      onFilesUploaded(uploadedFiles, isHandwritten);
    }
  };

  const clearFiles = () => {
    setUploadedFiles([]);
  };

  const removeFile = (index: number) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const FileIcon = ({ file }: { file: File }) => {
    return file.type === 'application/pdf' ? 
      <FileText className="h-4 w-4 text-destructive" /> : 
      <Image className="h-4 w-4 text-primary" />;
  };


  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold mb-2">Upload Medical Documents</h2>
        <p className="text-muted-foreground">
          Upload PDFs or images containing medical bills and prescriptions (including handwritten)
        </p>
      </div>

      {/* Handwritten Toggle */}
      <Card className="p-4">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            {isHandwritten ? <PenTool className="h-5 w-5 text-primary" /> : <FileCheck className="h-5 w-5 text-muted-foreground" />}
            <Label htmlFor="handwritten-mode" className="text-sm font-medium">
              {isHandwritten ? 'Handwritten Prescription Mode' : 'Standard Document Mode'}
            </Label>
          </div>
          <Switch
            id="handwritten-mode"
            checked={isHandwritten}
            onCheckedChange={setIsHandwritten}
            disabled={isProcessing}
          />
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          {isHandwritten 
            ? 'Enhanced OCR for handwritten prescriptions with better accuracy'
            : 'Standard processing for printed documents and clear text'
          }
        </p>
      </Card>

      <Card className="relative">
        <div
          {...dropzone.getRootProps()}
          className={cn(
            "border-2 border-dashed rounded-lg p-12 text-center transition-colors cursor-pointer",
            dropzone.isDragActive 
              ? "border-primary bg-primary-light" 
              : "border-border hover:border-primary/50",
            isProcessing && "opacity-50 cursor-not-allowed"
          )}
        >
          <input {...dropzone.getInputProps()} />
          <Upload className="mx-auto h-16 w-16 text-muted-foreground mb-6" />
          <h3 className="text-xl font-semibold mb-3">
            {isHandwritten ? 'Drop Handwritten Prescriptions Here' : 'Drop Medical Documents Here'}
          </h3>
          <p className="text-muted-foreground mb-4 text-lg">
            {isHandwritten 
              ? 'Upload handwritten prescriptions for enhanced OCR processing'
              : 'Upload PDFs or images containing bills and prescriptions'
            }
          </p>
          <div className="text-sm text-muted-foreground">
            Supports: PDF, PNG, JPG, JPEG
            {isHandwritten && <div className="text-primary font-medium mt-1">Enhanced handwriting recognition enabled</div>}
          </div>
        </div>
        
        {uploadedFiles.length > 0 && (
          <div className="mt-6 space-y-3">
            <h4 className="font-medium">Uploaded Files:</h4>
            {uploadedFiles.map((file, index) => (
              <div key={index} className="flex items-center justify-between bg-secondary rounded-md p-3">
                <div className="flex items-center gap-3">
                  <FileIcon file={file} />
                  <div>
                    <span className="text-sm font-medium">{file.name}</span>
                    <div className="text-xs text-muted-foreground">
                      {(file.size / 1024 / 1024).toFixed(1)} MB
                    </div>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeFile(index)}
                  disabled={isProcessing}
                  className="h-8 w-8 p-0"
                >
                  ×
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="flex justify-center gap-4">
        <Button
          onClick={clearFiles}
          variant="outline"
          disabled={isProcessing || uploadedFiles.length === 0}
        >
          Clear All Files
        </Button>
        <Button
          onClick={handleAnalyze}
          disabled={isProcessing || uploadedFiles.length === 0}
          className={cn(
            "shadow-medical",
            isHandwritten 
              ? "bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700" 
              : "bg-gradient-medical"
          )}
        >
          {isProcessing ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              {isHandwritten ? 'Processing Handwriting...' : 'Processing...'}
            </>
          ) : (
            <>
              {isHandwritten ? <PenTool className="mr-2 h-4 w-4" /> : null}
              {isHandwritten ? 'Analyze Handwritten Prescription' : 'Analyze Documents'}
            </>
          )}
        </Button>
      </div>
    </div>
  );
};