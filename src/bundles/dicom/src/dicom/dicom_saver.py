import datetime

import pydicom.uid

from pydicom.dataset import FileMetaDataset, Dataset
from pydicom.sequence import Sequence

from chimerax.core import version as chimerax_version

from .. import __version__ as dicom_bundle_version
from .dicom_models import DicomGrid

from chimerax.save_command import SaverInfo
from chimerax.map import Volume, Segmentation


class DicomSaver(SaverInfo):
    @property
    def save_args(self):
        from chimerax.core.commands import ModelsArg

        return {"models": ModelsArg}

    def save(self, session, path, *, models=None):
        # I anticipate there will be many edge cases to deal with when this is released in the wild.
        # As written, we assume that a unified seg file full of SourceImageSequence tags is the
        # canonical segmentation format. That could change!
        #
        # If you are maintaining this function: required attributes are assumed to exist and accessed
        # as dictionaries. Required, empty if absent attributes are accessed with .get(attr, "")
        """Save a DICOM segmentation as a DICOM SEG file. This function was adapted from code that
        was autogenerated by pydicom's codify utility script.

        Parameters:
        -----------
            path: str or None (default: None)
            models: list of models to save (default: None)
        """

        # Error out early if standard-required attributes are missing
        # We only care about Volumes and Segmentations; we can derive everything else from those

        volumes = []
        segmentations = []
        for model in list(models):
            if isinstance(model, Volume) and isinstance(model.data, DicomGrid):
                volumes.append(model)
            elif isinstance(model, Segmentation):
                segmentations.append(model)

        if not volumes and not segmentations:
            raise ValueError("No volumes or segmentations to save")

        for volume in volumes:
            if not volume.data:
                raise ValueError("Volume has no data")

        for segmentation in segmentations:
            if not segmentation.data:
                raise ValueError("Segmentation has no data")

        sample_file = self.reference_data.dicom_data.sample_file
        dt = datetime.datetime.now()
        date = dt.strftime("%Y%m%d")
        time = dt.strftime("%H%M%S.%f")
        pixel_spacing = list(self.reference_data.dicom_data.pixel_spacing()[:2])

        header = FileMetaDataset()
        ds = Dataset()

        header.FileMetaInformationGroupLength = 182
        header.FileMetaInformationVersion = b"\x00\x01"
        header.MediaStorageSOPClassUID = pydicom.uid.SegmentationStorage
        header.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
        # I think the Implementation Class UID is just the underlying library that pydicom uses,
        # but we should be gracious if corrected by the community on this.
        header.ImplementationClassUID = pydicom.uid.PYDICOM_IMPLEMENTATION_UID
        header.ImplementationVersionName = "pydicom-%s" % pydicom.__version__

        # region derive the Transfer Syntax UID
        ds.is_little_endian = sample_file.is_little_endian
        ds.is_implicit_VR = sample_file.is_implicit_VR

        if sample_file.is_little_endian and sample_file.is_implicit_VR:
            header.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
        elif sample_file.is_little_endian and not sample_file.is_implicit_VR:
            header.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
        elif not sample_file.is_little_endian and not sample_file.is_implicit_VR:
            header.TransferSyntaxUID = pydicom.uid.ExplicitVRBigEndian
        elif not sample_file.is_little_endian and sample_file.is_implicit_VR:
            # This is not a valid transfer syntax
            raise ValueError(
                "Cannot save DICOM SEG file with big endian implicit VR transfer syntax"
            )
        # endregion

        # *deep sigh* You might hope that these categories have disjoint information
        # but there is actually significant overlap. Data goes in whatever category
        # it's listed in first. DICOM is a mess. It's particularly a mess around the
        # Multi-Frame Functional Groups Sequence, Multi-frame Dimension, and Common
        # Instance Reference Modules, which are full of sequences of length 1 which
        # contain N sequences of 2 or 3 item sequences where N is the number of frames.
        # It's hard to read, but it's the DICOM standard.
        # region Patient
        ds.PatientName = sample_file.get("PatientName", "")
        ds.PatientID = sample_file.get("PatientID", "")
        ds.PatientBirthDate = sample_file.get("PatientBirthDate", "")
        ds.PatientSex = sample_file.get("PatientSex", "")
        # ds.PatientIdentityRemoved = sample_file.get("PatientIdentityRemoved", "NO")
        # endregion

        # region General Study
        ds.StudyDate = sample_file.get("StudyDate", "")
        ds.StudyTime = sample_file.get("StudyTime", "")
        # TODO: Who assigns these? Do we? Does the user? Required, Empty if Unknown
        ds.AccessionNumber = ""
        ds.ReferringPhysicianName = self.referring_pysician or ""
        ds.StudyInstanceUID = sample_file.get("StudyInstanceUID", "")
        ds.StudyID = ""  # TODO: Who assigns these? Do we? Does the user? Required, Empty if Unknown
        # endregion

        # region General Series
        ds.SeriesDate = sample_file.get("SeriesDate", "")
        ds.SeriesTime = sample_file.get("SeriesTime", "")
        ds.Modality = "SEG"
        ds.BodyPartExamined = sample_file.get("BodyPartExamined", "")
        ds.SeriesInstanceUID = pydicom.uid.generate_uid()  # TODO Make sure this is OK?
        ds.SeriesNumber = self.series_number or "1000"
        # endregion

        # region Segmentation Series
        # Modality handled in General Series
        # Series Number handled in General Series
        # endregion

        # region Frame of Reference
        ds.FrameOfReferenceUID = sample_file.get("FrameOfReferenceUID", "")
        ds.PositionReferenceIndicator = sample_file.get(
            "PositionReferenceIndicator", ""
        )
        # endregion

        # region General Equipment
        ds.Manufacturer = "UCSF ChimeraX"
        ds.ManufacturerModelName = "https://www.github.com/RBVI/ChimeraX"
        # ds.DeviceSerialNumber = ??
        ds.SoftwareVersions = f"UCSF ChimeraX {chimerax_version}, DICOM bundle version {dicom_bundle_version}"
        # endregion

        # region Enhanced General Equipment
        # endregion

        # region General Image
        ds.AcquisitionDate = date
        ds.ContentDate = date
        ds.AcquisitionTime = time
        ds.ContentTime = time
        # endregion

        # region General Reference
        # This isn't a _required_ attribute, but it's useful
        shared_functional_groups_sequence = Sequence()
        ds.SharedFunctionalGroupsSequence = shared_functional_groups_sequence

        shared_functional_groups = Dataset()
        derivation_image_sequence = Sequence()
        shared_functional_groups.DerivationImageSequence = derivation_image_sequence

        plane_orientation_sequence = Sequence()
        shared_functional_groups.PlaneOrientationSequence = plane_orientation_sequence

        plane_orientation = Dataset()
        plane_orientation.ImageOrientationPatient = (
            sample_file.ImageOrientationPatient
            or [
                1,
                0,
                0,
                0,
                1,
                0,
            ]
        )
        plane_orientation_sequence.append(plane_orientation)

        derivation_image = Dataset()
        source_image_sequence = Sequence()
        derivation_image.SourceImageSequence = source_image_sequence
        for index, frame in enumerate(self.pixel_array):
            source_image = Dataset()
            source_image.ReferencedSOPClassUID = sample_file.SOPClassUID
            source_image.ReferenceSOPInstanceUID = self.reference_data.dicom_data.files[
                index
            ].SOPInstanceUID
            source_image.ReferencedFrameNumber = "1"

            purpose_of_ref_code_sequence = Sequence()
            source_image.PurposeOfReferenceCodeSequence = purpose_of_ref_code_sequence

            purpose_of_ref_code = Dataset()
            purpose_of_ref_code.CodeValue = "121322"
            purpose_of_ref_code.CodingSchemeDesignator = "DCM"
            purpose_of_ref_code.CodeMeaning = (
                "Source image for image processing operation"
            )

            purpose_of_ref_code_sequence.append(purpose_of_ref_code)
            source_image_sequence.append(source_image)
        # endregion

        # region Image Pixel
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.NumberOfFrames = str(self.pixel_array.shape[0])
        ds.Rows = self.pixel_array.shape[1]
        ds.Columns = self.pixel_array.shape[2]
        ds.BitsAllocated = 1
        ds.BitsStored = 1
        ds.HighBit = 0
        ds.PixelRepresentation = 0
        ds.LossyImageCompression = "00"
        ds.SegmentationType = "BINARY"
        # endregion

        # region Segmentation Image
        # The standard mandates that DERIVED, PRIMARY is the only value for ImageType
        ds.ImageType = ["DERIVED", "PRIMARY"]
        ds.ContentLabel = self.content_label or ""
        ds.ContentCreatorName = self.content_creator_name or "UCSF ChimeraX"
        ds.ContentDescription = self.content_description or ""
        # endregion

        # TODO: Do we need this part?
        # Segment Sequence
        # segment_sequence = Sequence()
        # ds.SegmentSequence = segment_sequence
        # # Segment Sequence: Segment 1
        # segment1 = Dataset()
        #
        # # Segmented Property Category Code Sequence
        # segmented_property_category_code_sequence = Sequence()
        # segment1.SegmentedPropertyCategoryCodeSequence = segmented_property_category_code_sequence
        #
        # # Segmented Property Category Code Sequence: Segmented Property Category Code 1
        # segmented_property_category_code1 = Dataset()
        # segmented_property_category_code1.CodeValue = 'M-01000'
        # segmented_property_category_code1.CodingSchemeDesignator = 'SRT'
        # segmented_property_category_code1.CodeMeaning = 'Morphologically Altered Structure'
        # segmented_property_category_code_sequence.append(segmented_property_category_code1)
        #
        # segment1.SegmentNumber = 1
        # segment1.SegmentLabel = 'Segmentation'
        # segment1.SegmentAlgorithmType = 'SEMIAUTOMATIC'
        # segment1.SegmentAlgorithmName = 'alg01_run1'
        #
        # # Segmented Property Type Code Sequence
        # segmented_property_type_code_sequence = Sequence()
        # segment1.SegmentedPropertyTypeCodeSequence = segmented_property_type_code_sequence
        #
        # # Segmented Property Type Code Sequence: Segmented Property Type Code 1
        # segmented_property_type_code1 = Dataset()
        # segmented_property_type_code1.CodeValue = 'M-03000'
        # segmented_property_type_code1.CodingSchemeDesignator = 'SRT'
        # segmented_property_type_code1.CodeMeaning = 'Mass'
        # segmented_property_type_code_sequence.append(segmented_property_type_code1)
        # segment_sequence.append(segment1)

        segment = Dataset()
        segmented_property_category_code_sequence = Sequence()
        segment.SegmentedPropertyCategoryCodeSequence = (
            segmented_property_category_code_sequence
        )

        segmented_property_category_code = Dataset()
        segmented_property_category_code.CodeValue = "T-D0050"

        # region Multi-frame Functional Groups
        # Star of the show that makes the data sensible to ChimeraX and other programs
        derivation_code_sequence = Sequence()
        derivation_image.DerivationCodeSequence = derivation_code_sequence
        derivation_code = Dataset()
        derivation_code.CodeValue = "113076"
        derivation_code.CodingSchemeDesignator = "Segmentation"
        derivation_code.CodeMeaning = "Segmentation"
        derivation_code_sequence.append(derivation_code)
        derivation_image_sequence.append(derivation_image)

        pixel_measures_sequence = Sequence()
        shared_functional_groups.PixelMeasuresSequence = pixel_measures_sequence
        pixel_measures = Dataset()
        # pixel_measures.SliceThickness = "????" # TODO! Get this from the data!
        pixel_measures.PixelSpacing = pixel_spacing
        pixel_measures_sequence.append(pixel_measures)

        segment_identification_sequence = Sequence()
        shared_functional_groups.SegmentIdentificationSequence = (
            segment_identification_sequence
        )

        segment_identification = Dataset()
        segment_identification.ReferencedSegmentNumber = 1
        segment_identification_sequence.append(segment_identification)
        shared_functional_groups_sequence.append(shared_functional_groups)

        per_frame_functional_groups_sequence = Sequence()
        ds.PerFrameFunctionalGroupsSequence = per_frame_functional_groups_sequence

        for index, frame in enumerate(self.pixel_array):
            frame_content_sequence = Sequence()

            per_frame_functional_groups = Dataset()
            frame_content_sequence = Sequence()
            per_frame_functional_groups.FrameContentSequence = frame_content_sequence

            frame_content = Dataset()
            frame_content.StackID = "1"
            frame_content.InStackPositionNumber = index + 1
            frame_content.DimensionIndexValues = [1, index + 1]
            frame_content_sequence.append(frame_content)
            # # Plane Position Sequence
            plane_position_sequence = Sequence()
            per_frame_functional_groups.PlanePositionSequence = plane_position_sequence

            plane_position = Dataset()
            plane_position.ImagePositionPatient = self.reference_data.dicom_data.files[
                index
            ].get("ImagePositionPatient", "")
            plane_position_sequence.append(plane_position)
            per_frame_functional_groups_sequence.append(per_frame_functional_groups)

        # endregion

        # region Multi-frame Dimension
        dimension_organization_sequence = Sequence()
        ds.DimensionOrganizationSequence = dimension_organization_sequence
        dimension_organization = Dataset()
        dimension_organization.DimensionOrganizationUID = (
            pydicom.uid.generate_uid()
        )  # TODO: This OK?
        dimension_organization_sequence.append(dimension_organization)
        dimension_index_sequence = Sequence()
        ds.DimensionIndexSequence = dimension_index_sequence
        # Dimension Index Sequence: Dimension Index 1
        dimension_index1 = Dataset()
        dimension_index1.DimensionOrganizationUID = (
            "1.2.276.0.7230010.3.1.3.0.8180.1415310847.593768"
        )
        # dimension_index1.DimensionIndexPointer = (0020, 9056)
        # dimension_index1.FunctionalGroupPointer = (0020, 9111)
        dimension_index_sequence.append(dimension_index1)

        # Dimension Index Sequence: Dimension Index 2
        dimension_index2 = Dataset()
        dimension_index2.DimensionOrganizationUID = (
            "1.2.276.0.7230010.3.1.3.0.8180.1415310847.593768"
        )
        # dimension_index2.DimensionIndexPointer = (0020, 9057)
        # dimension_index2.FunctionalGroupPointer = (0020, 9111)
        dimension_index_sequence.append(dimension_index2)
        # endregion

        # region Common Instance Reference
        # This region is required when the segmentation references an instance in the same
        # study that the segmentation belongs to. I don't really get how that wouldn't always
        # be true.
        referenced_series_sequence = Sequence()
        ds.ReferencedSeriesSequence = referenced_series_sequence

        referenced_series = Dataset()
        referenced_instance_sequence = Sequence()
        referenced_series.ReferencedInstanceSequence = referenced_instance_sequence

        for index, _ in enumerate(self.pixel_array):
            referenced_file = self.reference_data.dicom_data.files[index]
            referenced_instance = Dataset()
            referenced_instance.ReferencedSOPClassUID = referenced_file.get(
                "SOPClassUID", ""
            )
            referenced_instance.ReferencedSOPInstanceUID = referenced_file.get(
                "SOPInstanceUID", ""
            )
            referenced_instance_sequence.append(referenced_instance)

        referenced_series.SeriesInstanceUID = sample_file.get("SeriesInstanceUID", "")
        referenced_series_sequence.append(referenced_series)

        studies_containing_other_referenced_instances_sequence = Sequence()
        ds.StudiesContainingOtherReferencedInstancesSequence = (
            studies_containing_other_referenced_instances_sequence
        )

        studies_containing_other_referenced_instances = Dataset()
        referenced_series_sequence = Sequence()
        studies_containing_other_referenced_instances.ReferencedSeriesSequence = (
            referenced_series_sequence
        )
        referenced_series = Dataset()
        referenced_instance_sequence = Sequence()
        referenced_series.ReferenceInstanceSequence = referenced_instance_sequence

        for index, _ in enumerate(self.pixel_array):
            referenced_file = self.reference_data.dicom_data.files[index]
            referenced_instance = Dataset()
            referenced_instance.ReferencedSOPClassUID = referenced_file.get(
                "SOPClassUID", ""
            )
            referenced_instance.ReferencedSOPInstanceUID = referenced_file.get(
                "SOPInstanceUID", ""
            )
            referenced_instance_sequence.append(referenced_instance)

        referenced_series.SeriesInstanceUID = sample_file.get("SeriesInstanceUID", "")
        referenced_series_sequence.append(referenced_series)

        studies_containing_other_referenced_instances.StudyInstanceUID = (
            sample_file.get("StudyInstanceUID", "")
        )
        studies_containing_other_referenced_instances_sequence.append(
            studies_containing_other_referenced_instances
        )

        # endregion

        # region SOP Common
        ds.SOPClassUID = pydicom.uid.SegmentationStorage
        # ds.InstanceCreatorUID = ??
        # ds.SOPInstanceUID = ??
        # endregion

        # For each frame of our segmentation, we need to associate it with some file in the reference
        # dataset, setting ReferencedSOPClassUID and ReferencedSOPInstanceUID. We derive these from the
        # images.
        # TODO: Will this sequence ever have more than one item?

        # We have to note that this segmentation is derived from a study containing this series, so
        # we need to add a ReferencedSeriesSequence to StudiesContainingOtherReferencedInstancesSequence
        # where we set the StudyInstanceUID attribute of ...

        # TODO Ensure this is correct
        from pydicom.pixel_data_handlers.util import pack_bits

        ds.PixelData = pack_bits(self.pixel_array)
        ds.file_meta = header
        ds.save_as(filename, write_like_original=False)
