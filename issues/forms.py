from django import forms
from django.core.exceptions import ValidationError
from .models import CivicIssue

ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/jpg']
MAX_IMAGE_SIZE_MB = 10


def validate_image_file(image):
    if image:
        if hasattr(image, 'content_type') and image.content_type not in ALLOWED_IMAGE_TYPES:
            raise ValidationError("Please upload a valid image file (JPEG, PNG, or WebP).")
        if hasattr(image, 'size') and image.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise ValidationError(f"Image size exceeds the maximum {MAX_IMAGE_SIZE_MB}MB limit.")
    return image


class PotholeReportForm(forms.ModelForm):
    image = forms.ImageField(required=False, validators=[validate_image_file])

    class Meta:
        model = CivicIssue
        fields = [
            'title',
            'description',
            'image',
            'latitude',
            'longitude',
            'location_name',
            'road_condition',
            'severity',
            'reporter_name',
            'reporter_contact',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'e.g., Deep pothole near College Main Gate'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe the road problem naturally (e.g., Two-wheelers are swerving and almost falling)...'
            }),
            'road_condition': forms.Select(attrs={'class': 'form-select'}),
            'severity': forms.Select(attrs={'class': 'form-select'}),
            'location_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Landmark or street address'
            }),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'reporter_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Name (Optional)'}),
            'reporter_contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone or Email for updates (Optional)'}),
        }


class WaterReportForm(forms.ModelForm):
    image = forms.ImageField(required=False, validators=[validate_image_file])

    class Meta:
        model = CivicIssue
        fields = [
            'title',
            'description',
            'image',
            'latitude',
            'longitude',
            'location_name',
            'water_problem_type',
            'water_duration',
            'affected_households',
            'reporter_name',
            'reporter_contact',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'e.g., No water supply since yesterday morning'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe the water problem (e.g., Complete outage across whole street, tap pressure zero)...'
            }),
            'water_problem_type': forms.Select(attrs={'class': 'form-select'}),
            'water_duration': forms.Select(attrs={'class': 'form-select'}),
            'affected_households': forms.Select(attrs={'class': 'form-select'}),
            'location_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Locality / Area landmark'
            }),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'reporter_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Name (Optional)'}),
            'reporter_contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone or Email for updates (Optional)'}),
        }


class WasteReportForm(forms.ModelForm):
    image = forms.ImageField(required=False, validators=[validate_image_file])

    class Meta:
        model = CivicIssue
        fields = [
            'title',
            'description',
            'image',
            'latitude',
            'longitude',
            'location_name',
            'waste_type',
            'waste_accumulation',
            'waste_duration',
            'reporter_name',
            'reporter_contact',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'e.g., Garbage bin overflowing near public park'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe the waste issue (e.g., Waste spilled over sidewalk, attracting stray animals)...'
            }),
            'waste_type': forms.Select(attrs={'class': 'form-select'}),
            'waste_accumulation': forms.Select(attrs={'class': 'form-select'}),
            'waste_duration': forms.Select(attrs={'class': 'form-select'}),
            'location_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Park / Street landmark'
            }),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'reporter_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Name (Optional)'}),
            'reporter_contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone or Email for updates (Optional)'}),
        }


class AdminActionForm(forms.ModelForm):
    resolution_image = forms.ImageField(required=False, validators=[validate_image_file])

    class Meta:
        model = CivicIssue
        fields = [
            'status',
            'assigned_department',
            'admin_action',
            'resolution_image',
            'resolution_note',
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select form-select-lg fw-bold'}),
            'assigned_department': forms.Select(attrs={'class': 'form-select'}),
            'admin_action': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter operational instructions, work order ID, or field notes...'
            }),
            'resolution_note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Explain how the issue was resolved, repair details, materials used...'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        resolution_note = cleaned_data.get('resolution_note')
        resolution_image = cleaned_data.get('resolution_image')

        # When marking as Resolved, encourage/require resolution proof details
        if status == CivicIssue.STATUS_RESOLVED:
            if not resolution_note and not self.instance.resolution_note:
                raise ValidationError({
                    'resolution_note': "A resolution note is required when marking an issue as Resolved to provide proof."
                })
        return cleaned_data
